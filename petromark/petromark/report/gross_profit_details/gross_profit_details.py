# Copyright (c) 2023, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_columns(filters):
	columns = [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Data" },
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Data" },

	]
	if not filters.get("update_stock"):
		columns += [
			{"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Data", "width": 180},
			{"label": _("Delivery Note Date"), "fieldname": "delivery_note_date", "fieldtype": "Data"},
		]

	columns += [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer"},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Data"},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data"},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data"},

	]

	if not filters.get("update_stock"):
		columns += [
			{"label": _("DN Qty"), "fieldname": "dn_qty", "fieldtype": "Float"},
		]
	columns += [
		{"label": _("SI Qty"), "fieldname": "si_qty", "fieldtype": "Float"},
		{"label": _("Selling Amount"), "fieldname": "selling_amount", "fieldtype": "Currency"},
		{"label": _("COGS"), "fieldname": "cogs", "fieldtype": "Currency", "width": 100},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency"},
		{"label": _("Gross Profit Percent"), "fieldname": "gross_profit_percent", "fieldtype": "Data"},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 200}
	]
	return columns


def get_conditions(filters):
	conditions = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " and SI.posting_date BETWEEN %(from_date)s and %(to_date)s"

	if filters.get("customer"):
		conditions += " and SI.customer=%(customer)s"

	if filters.get("sales_invoice"):
		conditions += " and SI.name=%(sales_invoice)s"

	conditions += " and SI.update_stock=%(update_stock)s"
	return conditions


def execute(filters=None):
	filters = frappe._dict(filters or {})

	# From Date / To Date are mandatory: they bound every heavy query below so the
	# report loads instantly instead of scanning the whole ledger.
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory."))

	# Normalise so it can be passed as a SQL bind value.
	filters["update_stock"] = 0 if not filters.get("update_stock") else 1

	columns = get_columns(filters)
	conditions = get_conditions(filters)

	sales_invoice = frappe.db.sql(""" SELECT
									SI.is_return,
									SI.name as sales_invoice,
									SI.posting_date as sales_invoice_date,
									SI.customer,
									SI.total_qty as si_qty,
									SI.grand_total as selling_amount
								FROM `tabSales Invoice` SI
								WHERE SI.docstatus=1 {0}
								ORDER BY SI.name ASC
							""".format(conditions), filters, as_dict=1)

	si_names = [x.sales_invoice for x in sales_invoice]

	# Only the invoice items belonging to the invoices in the selected date range are
	# ever used, so restrict the load instead of pulling the whole table.
	sales_invoice_items = frappe.db.sql(
		""" SELECT * FROM `tabSales Invoice Item` WHERE parent IN %(parents)s """,
		{"parents": si_names}, as_dict=1,
	) if si_names else []

	delivery_note_items = frappe.db.sql(""" SELECT DNI.*, DN.posting_date, DN.name as delivery_note FROM `tabDelivery Note`  DN
											INNER JOIN `tabDelivery Note Item` DNI ON DNI.parent = DN.name
											WHERE DN.docstatus=1 and DN.is_return = 0
											""", as_dict=1)

	stock_ledger_entry = frappe.db.sql(""" SELECT voucher_no, voucher_detail_no, item_code, stock_value_difference
										FROM `tabStock Ledger Entry` WHERE is_cancelled=0 """, as_dict=1)

	return_items = frappe.db.sql(""" SELECT SII.sales_invoice_item, SII.item_code, SI.status
									FROM `tabSales Invoice` SI
									INNER JOIN `tabSales Invoice Item` SII ON SII.parent = SI.name
									WHERE SI.is_return=1 and SI.docstatus=1 """, as_dict=1)

	# ---- Build lookup indexes so the per-invoice work is O(1) instead of scanning
	# ---- the full lists on every iteration (the original nested loops were the
	# ---- main reason the report took minutes to load).
	sii_by_parent = {}
	for it in sales_invoice_items:
		sii_by_parent.setdefault(it.parent, []).append(it)

	dni_by_si_detail = {}
	dni_by_name = {}
	for d in delivery_note_items:
		if d.get("si_detail"):
			dni_by_si_detail.setdefault(d.si_detail, []).append(d)
		dni_by_name[d.name] = d

	sle_by_detail = {}
	sle_by_voucher = {}
	for s in stock_ledger_entry:
		if s.get("voucher_detail_no"):
			sle_by_detail.setdefault(s.voucher_detail_no, []).append(s)
		sle_by_voucher.setdefault(s.voucher_no, []).append(s)

	return_sii = set(r.sales_invoice_item for r in return_items)

	indexes = frappe._dict({
		"sii_by_parent": sii_by_parent,
		"dni_by_si_detail": dni_by_si_detail,
		"dni_by_name": dni_by_name,
		"sle_by_detail": sle_by_detail,
		"sle_by_voucher": sle_by_voucher,
		"return_sii": return_sii,
	})

	data = []
	totals = {
		"sales_invoice": "Total",
		"si_qty": 0,
		"selling_amount": 0,
		"cogs": 0,
		"gross_profit": 0,
		'bold': True
	}
	delivery_notes = []
	counter = 0
	for idx, x in enumerate(sales_invoice):

		data.append(x)
		counter += 1
		sii, total, gross_profit, dn_name, dn_date, sis, si = get_sales_invoice_items(x, indexes, filters)
		if si:
			x['sales_invoice'] = sis['sis']
			x['sales_invoice_date'] = sis['dates']
			si_qty_total = 0
			for yx in sis['items']:
				si_qty_total += sis['items'][yx]
			x['si_qty'] = si_qty_total

			selling_amount_total = 0
			for yx in sis['rates']:
				selling_amount_total += sis['rates'][yx]
			x['selling_amount'] = selling_amount_total
		x['cogs'] = total
		x['gross_profit'] = x['selling_amount'] - x['cogs']
		x['gross_profit_percent'] = str(round(x['gross_profit'] / (x.selling_amount * 100 if x.selling_amount > 0 else 1),2)) + "%" if not x.is_return else str(round(x['gross_profit'] / (x.selling_amount * 100 if x.selling_amount > 0 else 1),2) * -1) + "%"
		x['bold'] = True
		x['delivery_note'] = dn_name
		x['delivery_note_date'] = dn_date

		x['dn_qty'] = 0

		totals['si_qty'] += x['si_qty']

		totals['selling_amount'] += x['selling_amount']
		totals['cogs'] += x['cogs']
		totals['gross_profit'] += x['gross_profit']
		totals['dn_qty'] = 0

		if 'delivery_note'in x and x['delivery_note'] and x['delivery_note'] in delivery_notes:
			del data[counter-1]
			counter -= 1
			continue
		if len(sii) > 0:
			for xxx in sii:
				check_return = xxx.name in indexes.return_sii
				# When the shared-delivery-note rate map (sis) does not contain this
				# item, it is not part of that DN's invoice set, so fall back to the
				# item's own Sales Invoice amount/qty instead of raising KeyError.
				amount = sis['rates'].get(xxx.item_code, xxx.amount) if si and isinstance(sis, dict) and sis.get('rates') else xxx.amount
				qty = sis['items'].get(xxx.item_code, xxx.qty) if si and isinstance(sis, dict) and sis.get('items') else xxx.qty
				objj = {
					"item_code": xxx.item_code,
					"item_name": xxx.item_name,
					"si_qty": qty,
					"warehouse": xxx.warehouse,
					"cogs": xxx['cogs'] ,
					"selling_amount": amount,
					"gross_profit": amount - (xxx['cogs']),
					"gross_profit_percent": str(round((( amount - (xxx['cogs'])) / amount) * 100,2)) + "%" if not x.is_return and amount > 0 else str(round((( amount - (xxx['cogs'])) / amount) * 100,2) * -1) + "%" if amount > 0 else 0,
					"parent_dn": dn_name

				}
				if check_return:
					objj['status'] = 'Credit Note Issued'
				if x.is_return:
					objj['status'] = 'Return'

				if not filters.get("update_stock"):
					objj['dn_qty'] = xxx['dn_qty']
					totals['dn_qty'] += xxx['dn_qty']
					x['dn_qty'] += xxx['dn_qty']
				data.append(objj)
				counter += 1

		if 'delivery_note' in x and x['delivery_note']:
			delivery_notes.append(x['delivery_note'])

	if totals['selling_amount'] > 0:
		totals['gross_profit_percent'] = str(round(totals['gross_profit'] / totals['selling_amount'] * 100,2)) + "%"
	data.append(totals)
	if not filters.get("update_stock") and filters.get("delivery_note"):
		data = [x for x in data if (x.get('delivery_note') and filters.get("delivery_note") == x.get('delivery_note')) or (x.get("parent_dn") and x.get("parent_dn") == filters.get("delivery_note"))]
	return columns, data


def get_sales_invoice_items(x, indexes, filters):
	items = []
	total = 0
	gross_profit = 0
	dn_name = ""
	dn_date = ""
	sis, si = {}, False
	items_ = []
	parent_items = indexes.sii_by_parent.get(x.sales_invoice, [])
	for xx in parent_items:
		items_.append(xx.item_code)
	for xx in parent_items:
		xx['dn_qty'], dn_names, dn_date, data = 0, "", "", []
		if not filters.get("update_stock"):
			xx['dn_qty'], dn_names, dn_date, data, sis, si = get_dn_details(xx, indexes)
		if dn_names:
			dn_names1 = dn_names.split(",")
			for xys in dn_names1:
				dns1 = dn_name.split(",")

				if xys not in dns1:
					if dn_name:
						dn_name += ","
					dn_name += xys
		xx['cogs'] = get_cogs(indexes, xx, data)
		total += (xx['cogs'])
		amount = 0
		if si:
			for y in sis['rates']:
				amount += sis['rates'][y]
		else:
			amount = xx.amount
		gross_profit = round(amount - (xx['cogs']),2)

		items.append(xx)
	dns = dn_name.split(",")
	other_items = []
	if len(dns) > 0:
		condition = ""
		if len(dns) == 1:
			condition += " SII.delivery_note=%(dn)s "
			cond_values = {"dn": dns[0]}
		else:
			condition += " SII.delivery_note in %(dn)s "
			cond_values = {"dn": tuple(dns)}
		si_ = frappe.db.sql(""" SELECT SI.name,SII.*, SI.posting_date FROM `tabSales Invoice` SI
								INNER JOIN `tabSales Invoice Item` SII ON SII.parent = SI.name
							  WHERE {0} and SI.docstatus=1
							""".format(condition), cond_values, as_dict=1)

		for yxx in si_:
			if yxx.item_code not in items_:
				items_.append(yxx.item_code)
				other_items.append(yxx)

	if len(other_items) > 0:
		for xx in other_items:
			xx['dn_qty'], dn_name, dn_date, data = 0, "", "", []
			if not filters.get("update_stock"):
				xx['dn_qty'], dn_names, dn_date, data, sis, si = get_dn_details(xx, indexes)

			xx['cogs'] = get_cogs(indexes, xx, data)

			total += (xx['cogs'])
			amount = 0
			if si:
				for y in sis['rates']:
					amount += sis['rates'][y]
			else:
				amount = xx.amount
			gross_profit = round(amount - (xx['cogs']),2)

			items.append(xx)
	return items, total, gross_profit, dn_name, dn_date, sis, si


def get_cogs(indexes, xx, dn_name):
	incoming_rate = 0
	if len(dn_name) == 0:
		for x in indexes.sle_by_detail.get(xx.name, []):
			if x.item_code == xx.item_code:
				incoming_rate += abs(x.stock_value_difference)
	else:
		for row in dn_name:
			if row[1]:
				for x in indexes.sle_by_voucher.get(row[1], []):
					if x.item_code == row[3]:
						incoming_rate += abs(x.stock_value_difference)
	return incoming_rate


def get_dn_details(xx, indexes):
	data = []
	qty = 0
	parents = ""
	posting_dates = ""
	sis = ""
	si = False
	if 'dn_detail' not in xx or not xx['dn_detail']:
		for x in indexes.dni_by_si_detail.get(xx.name, []):
			if parents:
				parents += ","
			if posting_dates:
				posting_dates += ","
			if x.qty - x.returned_qty > 0:
				data.append([x.qty, x.parent, x.posting_date, x.item_code])
				parents += x.parent
				posting_dates += str(x.posting_date)
			qty += (x.qty - x.returned_qty)

	else:
		si = True
		x = indexes.dni_by_name.get(xx.dn_detail)
		if x:
			if parents:
				parents += ","
			if posting_dates:
				posting_dates += ","
			if x.qty > 0:
				data.append([x.qty, x.parent, x.posting_date, x.item_code])
				parents += x.parent
				posting_dates += str(x.posting_date)
			qty += (x.qty - x.returned_qty)
			sis = check_dn(x)
	return qty, parents, posting_dates, data, sis, si


def check_dn(x):

	sis = ""
	dates = ""
	si = frappe.db.sql(""" SELECT SI.name,SII.item_code, SII.qty,SII.amount, SI.posting_date,SII.dn_detail FROM `tabSales Invoice` SI
						INNER JOIN `tabSales Invoice Item` SII ON SII.parent = SI.name
					  WHERE SII.delivery_note=%s and SI.docstatus=1
					""", x.delivery_note, as_dict=1)
	items = {}
	rates = {}
	for xx in si:
		if xx.name not in sis:
			if sis:
				sis += ","
			sis += xx.name
			if dates:
				dates += ","
			dates += str(xx.posting_date)
		if xx.item_code not in items:

			items[xx.item_code] = xx.qty
			rates[xx.item_code] = xx.amount
		elif xx.item_code in items:

			items[xx.item_code] += xx.qty
			rates[xx.item_code] += xx.amount
	return {
		"sis": sis,
		"items": items,
		"rates": rates,
		"dates": dates,
	}
