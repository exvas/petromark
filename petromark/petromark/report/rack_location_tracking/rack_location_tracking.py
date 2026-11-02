# Copyright (c) 2026, sammish and contributors
# For license information, please see license.txt

"""Rack Location Tracking.

A rack can be recorded in three different places and any of them can hold the
latest truth:

1. ``Purchase Receipt Item.logical_rack`` - the rack the goods were physically
   put in the last time they were received.
2. ``Logical Rack`` - the rack master, optionally scoped to a POS Profile.
3. ``Item.custom_rak_location`` - the rack kept on the item itself.

The POS resolves all three by date, so a rack typed on a fresh receipt shows up
on the POS screen without anybody touching the master. Reports that read only
the master therefore disagree with the POS. This report resolves the rack the
same way the POS does, and additionally shows every source side by side so the
difference between them can be found and corrected.
"""

import frappe
from frappe import _
from frappe.utils import cstr, flt, get_datetime, getdate

SOURCE_RECEIPT = "Purchase Receipt"
SOURCE_MASTER = "Rack Master"
SOURCE_ITEM = "Item Master"

STATUS_OK = "OK"
STATUS_MISMATCH = "Mismatch"
STATUS_NOT_IN_MASTER = "Not in Master"
STATUS_NO_RACK = "No Rack"


def execute(filters=None):
	filters = frappe._dict(filters or {})

	if not filters.get("company"):
		frappe.throw(_("Company is mandatory."))

	sources = _available_sources()
	if not sources["receipt"] and not sources["master"] and not sources["item"]:
		return (
			_columns_by_item(),
			[],
			_(
				"Rack tracking is not set up on this site. None of"
				" <b>Purchase Receipt Item.logical_rack</b>, the <b>Logical Rack</b>"
				" master or <b>Item.custom_rak_location</b> exists here."
			),
			None,
			None,
		)

	view = filters.get("view_type") or "Current Rack by Item"

	racks = _Racks(filters, sources)

	if view == "Receipt History":
		columns, data = _receipt_history(filters, racks)
	elif view == "Rack Occupancy":
		columns, data = _rack_occupancy(filters, racks)
	else:
		columns, data = _current_by_item(filters, racks)

	return columns, data, None, _chart(view, data), _summary(view, data)


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def _available_sources():
	"""Which of the three rack sources this site actually has."""
	receipt = frappe.get_meta("Purchase Receipt Item").has_field("logical_rack")
	master = frappe.db.table_exists("Logical Rack")
	item = frappe.get_meta("Item").has_field("custom_rak_location")
	return {"receipt": receipt, "master": master, "item": item}


class _Racks:
	"""Loads the three rack sources once and resolves them per item/warehouse.

	The precedence is the one the POS uses: whichever source was modified last
	wins, except that the item field is only consulted for items the other two
	never heard of. When a warehouse is known, receipts into that warehouse are
	preferred over receipts into any other.
	"""

	def __init__(self, filters, sources):
		self.filters = filters
		self.sources = sources
		self.warehouses = _warehouse_scope(filters)
		self.item_conditions, self.item_values = _item_scope(filters)

		self.master = self._load_master()
		self.receipts = self._load_receipts()
		self.item_racks = self._load_item_racks()
		self._cache = {}

	# -- loaders ----------------------------------------------------------

	def _load_master(self):
		"""{item: (rack, modified)} - newest master row per item."""
		if not self.sources["master"]:
			return {}

		conditions = ["ifnull(lr.rack_id, '') != ''"]
		values = {}
		if self.filters.get("pos_profile"):
			# rows without a profile are shared by every profile
			conditions.append("ifnull(lr.pos_profile, '') in ('', %(pos_profile)s)")
			values["pos_profile"] = self.filters.get("pos_profile")

		rows = frappe.db.sql(
			"""
			SELECT lr.item, lr.rack_id, lr.pos_profile, lr.modified
			FROM `tabLogical Rack` lr
			WHERE {conditions}
			""".format(conditions=" AND ".join(conditions)),
			values,
			as_dict=True,
		)

		master = {}
		for row in rows:
			if not row.item:
				continue
			current = master.get(row.item)
			if current and get_datetime(current[2]) >= get_datetime(row.modified):
				continue
			master[row.item] = (cstr(row.rack_id).strip(), row.pos_profile, row.modified)
		return master

	def _load_receipts(self):
		"""{item: [receipt rows]} - every submitted receipt that carries a rack."""
		if not self.sources["receipt"]:
			return {}

		conditions = ["pr.docstatus = 1", "ifnull(pri.logical_rack, '') != ''"]
		values = {"company": self.filters.get("company")}
		conditions.append("pr.company = %(company)s")

		if self.item_conditions:
			conditions.append(self.item_conditions)
			values.update(self.item_values)
		if self.warehouses is not None:
			conditions.append("pri.warehouse in %(warehouses)s")
			values["warehouses"] = self.warehouses
		if self.filters.get("purchase_receipt"):
			conditions.append("pri.parent = %(purchase_receipt)s")
			values["purchase_receipt"] = self.filters.get("purchase_receipt")
		if self.filters.get("supplier"):
			conditions.append("pr.supplier = %(supplier)s")
			values["supplier"] = self.filters.get("supplier")

		rows = frappe.db.sql(
			"""
			SELECT
				pri.item_code, pri.item_name, pri.logical_rack AS rack,
				pri.warehouse, pri.qty, pri.stock_qty, pri.stock_uom,
				pri.modified, pri.parent AS purchase_receipt,
				pr.posting_date, pr.supplier, pr.supplier_name
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE {conditions}
			ORDER BY pr.posting_date DESC, pri.modified DESC
			""".format(conditions=" AND ".join(conditions)),
			values,
			as_dict=True,
		)

		receipts = {}
		for row in rows:
			row.rack = cstr(row.rack).strip()
			receipts.setdefault(row.item_code, []).append(row)
		return receipts

	def _load_item_racks(self):
		"""{item: (rack, modified)} - the rack kept on the item itself."""
		if not self.sources["item"]:
			return {}

		conditions = ["ifnull(item.custom_rak_location, '') != ''"]
		values = {}
		if self.item_conditions:
			conditions.append(self.item_conditions.replace("pri.item_code", "item.name"))
			values.update(self.item_values)

		rows = frappe.db.sql(
			"""
			SELECT item.name, item.custom_rak_location AS rack, item.modified
			FROM `tabItem` item
			WHERE {conditions}
			""".format(conditions=" AND ".join(conditions)),
			values,
			as_dict=True,
		)
		return {row.name: (cstr(row.rack).strip(), row.modified) for row in rows}

	# -- resolution -------------------------------------------------------

	def latest_receipt(self, item_code, warehouse=None):
		"""The receipt row whose rack is in force for this item/warehouse."""
		rows = self.receipts.get(item_code)
		if not rows:
			return None
		# a rack belongs to a warehouse, so only look elsewhere when the item
		# was never received into the warehouse we are asking about
		preferred = [r for r in rows if r.warehouse == warehouse] if warehouse else []
		return max(preferred or rows, key=lambda r: get_datetime(r.modified))

	def resolve(self, item_code, warehouse=None):
		"""(rack, source, receipt_row) for an item in a warehouse."""
		key = (item_code, warehouse)
		if key in self._cache:
			return self._cache[key]

		best = None  # (rack, source, modified)

		master = self.master.get(item_code)
		if master and master[0]:
			best = (master[0], SOURCE_MASTER, master[2])

		receipt = self.latest_receipt(item_code, warehouse)
		if receipt and receipt.rack:
			if not best or get_datetime(receipt.modified) > get_datetime(best[2]):
				best = (receipt.rack, SOURCE_RECEIPT, receipt.modified)

		if not best:
			on_item = self.item_racks.get(item_code)
			if on_item and on_item[0]:
				best = (on_item[0], SOURCE_ITEM, on_item[1])

		result = (best[0], best[1], receipt) if best else ("", "", receipt)
		self._cache[key] = result
		return result

	def master_rack(self, item_code):
		master = self.master.get(item_code)
		return master[0] if master else ""

	def item_rack(self, item_code):
		on_item = self.item_racks.get(item_code)
		return on_item[0] if on_item else ""


# ---------------------------------------------------------------------------
# scope helpers
# ---------------------------------------------------------------------------


def _warehouse_scope(filters):
	"""The warehouses in scope, or None when every warehouse is in scope."""
	warehouse = filters.get("warehouse")
	if not warehouse:
		return None

	bounds = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=True)
	if not bounds:
		return [warehouse]

	children = frappe.db.sql_list(
		"""SELECT name FROM `tabWarehouse` WHERE lft >= %s AND rgt <= %s""",
		(bounds.lft, bounds.rgt),
	)
	return children or [warehouse]


def _item_scope(filters):
	"""An SQL condition on pri.item_code for the item filters, plus its values."""
	conditions = []
	values = {}

	if filters.get("item_code"):
		conditions.append("pri.item_code = %(item_code)s")
		values["item_code"] = filters.get("item_code")
	if filters.get("item_group"):
		group = frappe.db.get_value("Item Group", filters.get("item_group"), ["lft", "rgt"], as_dict=True)
		if group:
			conditions.append(
				"""pri.item_code in (SELECT name FROM `tabItem` WHERE item_group in
					(SELECT name FROM `tabItem Group` WHERE lft >= %(ig_lft)s AND rgt <= %(ig_rgt)s))"""
			)
			values["ig_lft"] = group.lft
			values["ig_rgt"] = group.rgt
		else:
			conditions.append("pri.item_code in (SELECT name FROM `tabItem` WHERE item_group = %(item_group)s)")
			values["item_group"] = filters.get("item_group")
	if filters.get("brand"):
		conditions.append("pri.item_code in (SELECT name FROM `tabItem` WHERE brand = %(brand)s)")
		values["brand"] = filters.get("brand")

	return " AND ".join(conditions), values


def _item_details(item_codes):
	if not item_codes:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT name, item_name, item_group, brand, stock_uom, disabled
		FROM `tabItem`
		WHERE name in %(item_codes)s
		""",
		{"item_codes": list(item_codes)},
		as_dict=True,
	)
	return {row.name: row for row in rows}


def _stock(filters, racks):
	"""{(item, warehouse): bin row} for every item that has a bin in scope."""
	conditions = ["bin.company = %(company)s"] if frappe.get_meta("Bin").has_field("company") else []
	values = {"company": filters.get("company")}

	if not conditions:
		# older schemas keep the company on the warehouse
		conditions = [
			"bin.warehouse in (SELECT name FROM `tabWarehouse` WHERE company = %(company)s)"
		]

	if racks.warehouses is not None:
		conditions.append("bin.warehouse in %(warehouses)s")
		values["warehouses"] = racks.warehouses
	if racks.item_conditions:
		conditions.append(racks.item_conditions.replace("pri.item_code", "bin.item_code"))
		values.update(racks.item_values)

	rows = frappe.db.sql(
		"""
		SELECT bin.item_code, bin.warehouse, bin.actual_qty, bin.stock_value,
			bin.valuation_rate
		FROM `tabBin` bin
		WHERE {conditions}
		""".format(conditions=" AND ".join(conditions)),
		values,
		as_dict=True,
	)
	return {(row.item_code, row.warehouse): row for row in rows}


def _status(resolved_rack, master, source):
	if not resolved_rack:
		return STATUS_NO_RACK
	if not master:
		return STATUS_NOT_IN_MASTER
	if master != resolved_rack:
		return STATUS_MISMATCH
	return STATUS_OK


def _keep(filters, status):
	wanted = filters.get("status")
	if not wanted or wanted == "All":
		return True
	if wanted == "Needs Attention":
		return status in (STATUS_MISMATCH, STATUS_NOT_IN_MASTER, STATUS_NO_RACK)
	return status == wanted


# ---------------------------------------------------------------------------
# view: Current Rack by Item
# ---------------------------------------------------------------------------


def _current_by_item(filters, racks):
	stock = _stock(filters, racks)

	pairs = set(stock.keys())

	# items whose rack is only known from a receipt, even if the bin is gone
	for item_code, rows in racks.receipts.items():
		for row in rows:
			pairs.add((item_code, row.warehouse))

	# items only the master knows about get the warehouse of their POS profile
	if racks.master:
		profile_warehouse = dict(
			frappe.db.sql("""SELECT name, warehouse FROM `tabPOS Profile`""") or []
		)
		for item_code, (rack, pos_profile, _modified) in racks.master.items():
			warehouse = profile_warehouse.get(pos_profile)
			if warehouse and (racks.warehouses is None or warehouse in racks.warehouses):
				pairs.add((item_code, warehouse))

	items = _item_details({item for item, _wh in pairs})

	# honour the item filters for pairs that did not come through a filtered query
	if filters.get("item_code"):
		pairs = {p for p in pairs if p[0] == filters.get("item_code")}
	if filters.get("brand"):
		pairs = {p for p in pairs if (items.get(p[0]) or {}).get("brand") == filters.get("brand")}

	show_zero = filters.get("show_zero_stock")
	rack_filter = cstr(filters.get("rack_id")).strip().lower()

	data = []
	for item_code, warehouse in pairs:
		item = items.get(item_code)
		if not item:
			continue

		bin_row = stock.get((item_code, warehouse))
		qty = flt(bin_row.actual_qty) if bin_row else 0.0
		if not qty and not show_zero:
			continue

		rack, source, receipt = racks.resolve(item_code, warehouse)
		master = racks.master_rack(item_code)
		status = _status(rack, master, source)

		if not _keep(filters, status):
			continue
		if rack_filter and rack_filter not in rack.lower():
			continue

		data.append(
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"item_group": item.item_group,
				"brand": item.brand,
				"warehouse": warehouse,
				"current_rack": rack,
				"rack_source": source,
				"master_rack": master,
				"receipt_rack": receipt.rack if receipt else "",
				"item_rack": racks.item_rack(item_code),
				"last_receipt": receipt.purchase_receipt if receipt else None,
				"last_receipt_date": receipt.posting_date if receipt else None,
				"supplier": receipt.supplier if receipt else None,
				"stock_qty": qty,
				"stock_uom": item.stock_uom,
				"stock_value": flt(bin_row.stock_value) if bin_row else 0.0,
				"status": status,
			}
		)

	data.sort(key=lambda r: (r["current_rack"] or "zzz", r["item_code"]))
	return _columns_by_item(), data


def _columns_by_item():
	return [
		_col(_("Item"), "item_code", "Link", 110, options="Item"),
		_col(_("Item Name"), "item_name", width=200),
		_col(_("Current Rack"), "current_rack", width=120),
		_col(_("Source"), "rack_source", width=120),
		_col(_("Status"), "status", width=120),
		_col(_("Rack Master"), "master_rack", width=110),
		_col(_("Rack on Receipt"), "receipt_rack", width=120),
		_col(_("Warehouse"), "warehouse", "Link", 150, options="Warehouse"),
		_col(_("Stock Qty"), "stock_qty", "Float", 100),
		_col(_("UOM"), "stock_uom", "Link", 70, options="UOM"),
		_col(_("Stock Value"), "stock_value", "Currency", 120),
		_col(_("Last Receipt"), "last_receipt", "Link", 150, options="Purchase Receipt"),
		_col(_("Received On"), "last_receipt_date", "Date", 100),
		_col(_("Supplier"), "supplier", "Link", 140, options="Supplier"),
		_col(_("Item Group"), "item_group", "Link", 130, options="Item Group"),
		_col(_("Brand"), "brand", "Link", 110, options="Brand"),
		_col(_("Rack on Item"), "item_rack", width=110),
	]


# ---------------------------------------------------------------------------
# view: Receipt History
# ---------------------------------------------------------------------------


def _receipt_history(filters, racks):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	rack_filter = cstr(filters.get("rack_id")).strip().lower()

	items = _item_details(set(racks.receipts.keys()))

	data = []
	for item_code, rows in racks.receipts.items():
		item = items.get(item_code) or frappe._dict()
		master = racks.master_rack(item_code)

		for row in rows:
			if from_date and getdate(row.posting_date) < getdate(from_date):
				continue
			if to_date and getdate(row.posting_date) > getdate(to_date):
				continue
			if rack_filter and rack_filter not in row.rack.lower():
				continue

			in_force = racks.latest_receipt(item_code, row.warehouse)
			is_current = bool(in_force and in_force.purchase_receipt == row.purchase_receipt)
			status = _status(row.rack, master, SOURCE_RECEIPT)

			if not _keep(filters, status):
				continue

			data.append(
				{
					"posting_date": row.posting_date,
					"purchase_receipt": row.purchase_receipt,
					"supplier": row.supplier,
					"supplier_name": row.supplier_name,
					"item_code": item_code,
					"item_name": row.item_name or item.get("item_name"),
					"item_group": item.get("item_group"),
					"brand": item.get("brand"),
					"warehouse": row.warehouse,
					"qty": flt(row.stock_qty) or flt(row.qty),
					"stock_uom": row.stock_uom or item.get("stock_uom"),
					"rack": row.rack,
					"master_rack": master,
					"in_force": _("Yes") if is_current else _("No"),
					"status": status,
				}
			)

	data.sort(key=lambda r: (getdate(r["posting_date"]), r["purchase_receipt"], r["item_code"]), reverse=True)
	return _columns_receipt_history(), data


def _columns_receipt_history():
	return [
		_col(_("Date"), "posting_date", "Date", 95),
		_col(_("Purchase Receipt"), "purchase_receipt", "Link", 160, options="Purchase Receipt"),
		_col(_("Item"), "item_code", "Link", 110, options="Item"),
		_col(_("Item Name"), "item_name", width=200),
		_col(_("Rack Put In"), "rack", width=120),
		_col(_("Rack Master"), "master_rack", width=110),
		_col(_("Status"), "status", width=120),
		_col(_("In Force"), "in_force", width=80),
		_col(_("Qty"), "qty", "Float", 90),
		_col(_("UOM"), "stock_uom", "Link", 70, options="UOM"),
		_col(_("Warehouse"), "warehouse", "Link", 150, options="Warehouse"),
		_col(_("Supplier"), "supplier", "Link", 140, options="Supplier"),
		_col(_("Supplier Name"), "supplier_name", width=170),
		_col(_("Item Group"), "item_group", "Link", 130, options="Item Group"),
		_col(_("Brand"), "brand", "Link", 110, options="Brand"),
	]


# ---------------------------------------------------------------------------
# view: Rack Occupancy
# ---------------------------------------------------------------------------


def _rack_occupancy(filters, racks):
	_columns, rows = _current_by_item(filters, racks)

	buckets = {}
	for row in rows:
		key = (row["current_rack"] or _("(no rack)"), row["warehouse"])
		bucket = buckets.setdefault(
			key,
			{
				"rack_id": key[0],
				"warehouse": key[1],
				"item_count": 0,
				"total_qty": 0.0,
				"total_value": 0.0,
				"mismatch_count": 0,
				"items": [],
			},
		)
		bucket["item_count"] += 1
		bucket["total_qty"] += flt(row["stock_qty"])
		bucket["total_value"] += flt(row["stock_value"])
		if row["status"] in (STATUS_MISMATCH, STATUS_NOT_IN_MASTER):
			bucket["mismatch_count"] += 1
		if len(bucket["items"]) < 12:
			bucket["items"].append(row["item_code"])

	data = []
	for bucket in buckets.values():
		bucket["items"] = ", ".join(bucket["items"])
		data.append(bucket)

	data.sort(key=lambda r: (-flt(r["total_value"]), r["rack_id"]))
	return _columns_occupancy(), data


def _columns_occupancy():
	return [
		_col(_("Rack"), "rack_id", width=140),
		_col(_("Warehouse"), "warehouse", "Link", 170, options="Warehouse"),
		_col(_("Items"), "item_count", "Int", 90),
		_col(_("Total Qty"), "total_qty", "Float", 110),
		_col(_("Stock Value"), "total_value", "Currency", 130),
		_col(_("Needs Attention"), "mismatch_count", "Int", 130),
		_col(_("Item Codes"), "items", width=320),
	]


# ---------------------------------------------------------------------------
# presentation
# ---------------------------------------------------------------------------


def _col(label, fieldname, fieldtype="Data", width=120, options=None):
	column = {"label": label, "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
	if options:
		column["options"] = options
	return column


def _chart(view, data):
	if not data:
		return None

	if view == "Rack Occupancy":
		top = data[:15]
		labels = [row["rack_id"] for row in top]
		values = [flt(row["total_value"]) for row in top]
		title = _("Stock Value by Rack")
	else:
		buckets = {}
		for row in data:
			rack = row.get("current_rack") or row.get("rack") or _("(no rack)")
			buckets[rack] = buckets.get(rack, 0) + 1
		top = sorted(buckets.items(), key=lambda kv: -kv[1])[:15]
		labels = [item[0] for item in top]
		values = [item[1] for item in top]
		title = _("Items per Rack")

	return {
		"data": {"labels": labels, "datasets": [{"name": title, "values": values}]},
		"type": "bar",
		"colors": ["#449CF0"],
		"fieldtype": "Float",
	}


def _summary(view, data):
	if not data:
		return None

	if view == "Rack Occupancy":
		return [
			{"label": _("Racks"), "value": len(data), "indicator": "Blue"},
			{
				"label": _("Items Placed"),
				"value": sum(row["item_count"] for row in data),
				"indicator": "Blue",
			},
			{
				"label": _("Stock Value"),
				"value": sum(flt(row["total_value"]) for row in data),
				"datatype": "Currency",
				"indicator": "Green",
			},
			{
				"label": _("Needs Attention"),
				"value": sum(row["mismatch_count"] for row in data),
				"indicator": "Orange",
			},
		]

	statuses = [row.get("status") for row in data]
	racks = {row.get("current_rack") or row.get("rack") for row in data}
	racks.discard("")

	summary = [
		{"label": _("Rows"), "value": len(data), "indicator": "Blue"},
		{"label": _("Racks Used"), "value": len(racks), "indicator": "Blue"},
		{
			"label": _("Mismatch"),
			"value": statuses.count(STATUS_MISMATCH),
			"indicator": "Red" if statuses.count(STATUS_MISMATCH) else "Green",
		},
		{
			"label": _("Not in Master"),
			"value": statuses.count(STATUS_NOT_IN_MASTER),
			"indicator": "Orange" if statuses.count(STATUS_NOT_IN_MASTER) else "Green",
		},
	]

	if view != "Receipt History":
		no_rack = statuses.count(STATUS_NO_RACK)
		summary.append(
			{"label": _("No Rack"), "value": no_rack, "indicator": "Orange" if no_rack else "Green"}
		)

	return summary
