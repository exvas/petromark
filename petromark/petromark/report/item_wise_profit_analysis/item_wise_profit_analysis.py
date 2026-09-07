# Copyright (c) 2026, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	view = filters.get("view_type") or "Item Summary"

	if view == "Transaction":
		columns, data = get_transaction_view(filters)
	elif view == "Item - Monthly":
		columns, data = get_monthly_view(filters)
	else:
		columns, data = get_summary_view(filters)

	report_summary = build_report_summary(data)
	chart = build_chart(view, data)
	return columns, data, None, chart, report_summary


# ---------------------------------------------------------------------------
# Conditions (all values passed as bind parameters -> no SQL injection)
# ---------------------------------------------------------------------------
def sales_conditions(filters):
	c = " AND IFNULL(si.is_opening,'No') <> 'Yes' AND IFNULL(sii.item_code,'') <> '' "
	if filters.get("from_date") and filters.get("to_date"):
		c += " AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s "
	if filters.get("company"):
		c += " AND si.company = %(company)s "
	if filters.get("customer"):
		c += " AND si.customer = %(customer)s "
	if filters.get("item_group"):
		c += " AND sii.item_group = %(item_group)s "
	if filters.get("brand"):
		c += " AND sii.brand = %(brand)s "
	if filters.get("item_code"):
		c += " AND sii.item_code = %(item_code)s "
	if filters.get("warehouse"):
		c += " AND sii.warehouse = %(warehouse)s "
	return c


def purchase_conditions(filters):
	c = " AND IFNULL(pi.is_opening,'No') <> 'Yes' AND IFNULL(pii.item_code,'') <> '' "
	if filters.get("from_date") and filters.get("to_date"):
		c += " AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s "
	if filters.get("company"):
		c += " AND pi.company = %(company)s "
	if filters.get("item_group"):
		c += " AND pii.item_group = %(item_group)s "
	if filters.get("brand"):
		c += " AND pii.brand = %(brand)s "
	if filters.get("item_code"):
		c += " AND pii.item_code = %(item_code)s "
	if filters.get("warehouse"):
		c += " AND pii.warehouse = %(warehouse)s "
	return c


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------
def get_sales_data(filters, monthly=False):
	month_col = ", DATE_FORMAT(si.posting_date, '%%Y-%%m') AS month" if monthly else ""
	month_grp = ", DATE_FORMAT(si.posting_date, '%%Y-%%m')" if monthly else ""
	return frappe.db.sql(
		"""
		SELECT
			sii.item_code AS item_code,
			MAX(sii.item_name) AS item_name,
			MAX(sii.item_group) AS item_group,
			MAX(sii.brand) AS brand
			{month_col},
			SUM(sii.stock_qty) AS sold_qty,
			SUM(sii.base_net_amount) AS revenue,
			SUM(sii.incoming_rate * sii.stock_qty) AS cogs,
			COUNT(DISTINCT si.name) AS num_invoices
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 {conditions}
		GROUP BY sii.item_code {month_grp}
		""".format(month_col=month_col, month_grp=month_grp, conditions=sales_conditions(filters)),
		filters, as_dict=1,
	)


def get_purchase_data(filters, monthly=False):
	month_col = ", DATE_FORMAT(pi.posting_date, '%%Y-%%m') AS month" if monthly else ""
	month_grp = ", DATE_FORMAT(pi.posting_date, '%%Y-%%m')" if monthly else ""
	rows = frappe.db.sql(
		"""
		SELECT
			pii.item_code AS item_code,
			MAX(pii.item_name) AS item_name,
			MAX(pii.item_group) AS item_group,
			MAX(pii.brand) AS brand
			{month_col},
			SUM(pii.stock_qty) AS purchased_qty,
			SUM(pii.base_net_amount) AS purchase_amount
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1 {conditions}
		GROUP BY pii.item_code {month_grp}
		""".format(month_col=month_col, month_grp=month_grp, conditions=purchase_conditions(filters)),
		filters, as_dict=1,
	)
	key = (lambda r: (r.item_code, r.month)) if monthly else (lambda r: r.item_code)
	return {key(r): r for r in rows}


def get_stock_data(filters):
	cond = ""
	if filters.get("warehouse"):
		cond += " AND b.warehouse = %(warehouse)s "
	rows = frappe.db.sql(
		"""
		SELECT b.item_code AS item_code,
			SUM(b.actual_qty) AS stock_qty,
			SUM(b.stock_value) AS stock_value
		FROM `tabBin` b
		WHERE 1=1 {cond}
		GROUP BY b.item_code
		""".format(cond=cond),
		filters, as_dict=1,
	)
	return {r.item_code: r for r in rows}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
def _profit_fields(row):
	revenue = flt(row.get("revenue"))
	cogs = flt(row.get("cogs"))
	sold_qty = flt(row.get("sold_qty"))
	gross_profit = revenue - cogs
	row["cogs"] = cogs
	row["gross_profit"] = gross_profit
	row["margin_pct"] = (gross_profit / revenue * 100) if revenue else 0
	row["avg_selling_rate"] = (revenue / sold_qty) if sold_qty else 0
	row["avg_cost_rate"] = (cogs / sold_qty) if sold_qty else 0
	return row


def get_summary_view(filters):
	show_ps = int(filters.get("show_purchase_stock") or 0)
	sales = get_sales_data(filters)
	rows_by_item = {}

	for r in sales:
		rows_by_item[r.item_code] = _profit_fields(r)

	if show_ps:
		purchase = get_purchase_data(filters)
		stock = get_stock_data(filters)
		# include items purchased in the period even if not sold
		for item_code, p in purchase.items():
			row = rows_by_item.get(item_code)
			if not row:
				row = frappe._dict({
					"item_code": item_code, "item_name": p.item_name,
					"item_group": p.item_group, "brand": p.brand,
					"sold_qty": 0, "revenue": 0, "cogs": 0, "num_invoices": 0,
				})
				_profit_fields(row)
				rows_by_item[item_code] = row
			row["purchased_qty"] = flt(p.purchased_qty)
			row["purchase_amount"] = flt(p.purchase_amount)
		for item_code, s in stock.items():
			if item_code in rows_by_item:
				rows_by_item[item_code]["stock_qty"] = flt(s.stock_qty)
				rows_by_item[item_code]["stock_value"] = flt(s.stock_value)

	data = list(rows_by_item.values())
	data.sort(key=_sort_key(filters), reverse=True)

	totals = _totals_row(data, show_ps)
	if data:
		data.append(totals)
	return get_columns("Item Summary", show_ps), data


def get_monthly_view(filters):
	show_ps = int(filters.get("show_purchase_stock") or 0)
	sales = get_sales_data(filters, monthly=True)
	rows = {}
	for r in sales:
		rows[(r.item_code, r.month)] = _profit_fields(r)

	if show_ps:
		purchase = get_purchase_data(filters, monthly=True)
		for k, p in purchase.items():
			row = rows.get(k)
			if not row:
				row = frappe._dict({
					"item_code": k[0], "month": k[1], "item_name": p.item_name,
					"item_group": p.item_group, "brand": p.brand,
					"sold_qty": 0, "revenue": 0, "cogs": 0, "num_invoices": 0,
				})
				_profit_fields(row)
				rows[k] = row
			row["purchased_qty"] = flt(p.purchased_qty)
			row["purchase_amount"] = flt(p.purchase_amount)

	data = list(rows.values())
	data.sort(key=lambda r: (r.get("item_code") or "", r.get("month") or ""))
	totals = _totals_row(data, show_ps)
	if data:
		data.append(totals)
	return get_columns("Item - Monthly", show_ps), data


def get_transaction_view(filters):
	rows = frappe.db.sql(
		"""
		SELECT
			si.posting_date AS posting_date,
			si.name AS sales_invoice,
			si.customer AS customer,
			sii.item_code AS item_code,
			sii.item_name AS item_name,
			sii.item_group AS item_group,
			sii.brand AS brand,
			sii.warehouse AS warehouse,
			sii.stock_qty AS sold_qty,
			sii.base_net_amount AS revenue,
			(sii.incoming_rate * sii.stock_qty) AS cogs
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 {conditions}
		ORDER BY si.posting_date ASC, si.name ASC
		""".format(conditions=sales_conditions(filters)),
		filters, as_dict=1,
	)
	data = []
	for r in rows:
		revenue = flt(r.revenue)
		cogs = flt(r.cogs)
		qty = flt(r.sold_qty)
		r["cogs"] = cogs
		r["gross_profit"] = revenue - cogs
		r["margin_pct"] = ((revenue - cogs) / revenue * 100) if revenue else 0
		r["avg_selling_rate"] = (revenue / qty) if qty else 0
		r["avg_cost_rate"] = (cogs / qty) if qty else 0
		data.append(r)
	totals = _totals_row(data, show_ps=0)
	if data:
		data.append(totals)
	return get_columns("Transaction", 0), data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sort_key(filters):
	by = filters.get("sort_by") or "Gross Profit"
	field = {
		"Gross Profit": "gross_profit",
		"Sales Amount": "revenue",
		"Sold Qty": "sold_qty",
		"Margin %": "margin_pct",
	}.get(by, "gross_profit")
	return lambda r: flt(r.get(field))


def _totals_row(data, show_ps):
	totals = frappe._dict({"item_code": "Total", "item_name": "", "bold": 1})
	for f in ["sold_qty", "revenue", "cogs", "gross_profit", "num_invoices",
			"purchased_qty", "purchase_amount", "stock_qty", "stock_value"]:
		totals[f] = sum(flt(r.get(f)) for r in data)
	totals["margin_pct"] = (totals["gross_profit"] / totals["revenue"] * 100) if totals["revenue"] else 0
	return totals


def get_columns(view, show_ps):
	cols = []
	if view == "Transaction":
		cols += [
			{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
			{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
			{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		]
	elif view == "Item - Monthly":
		cols += [{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 90}]

	cols += [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 100},
	]
	if view == "Transaction":
		cols += [{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130}]

	cols += [
		{"label": _("Sold Qty"), "fieldname": "sold_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Sales Amount"), "fieldname": "revenue", "fieldtype": "Currency", "width": 120},
		{"label": _("COGS"), "fieldname": "cogs", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Margin %"), "fieldname": "margin_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Avg Selling Rate"), "fieldname": "avg_selling_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Avg Cost Rate"), "fieldname": "avg_cost_rate", "fieldtype": "Currency", "width": 120},
	]

	if view != "Transaction":
		cols += [{"label": _("Sales Invoices"), "fieldname": "num_invoices", "fieldtype": "Int", "width": 100}]

	if show_ps and view != "Transaction":
		cols += [
			{"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "width": 110},
			{"label": _("Purchase Amount"), "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 130},
		]
		if view == "Item Summary":
			cols += [
				{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 100},
				{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
			]
	return cols


# ---------------------------------------------------------------------------
# Small dashboard: summary number cards + chart
# ---------------------------------------------------------------------------
def build_report_summary(data):
	body = [r for r in data if (r.get("item_code") != "Total") and not r.get("bold")]
	tot = next((r for r in data if r.get("item_code") == "Total"), None)
	if not tot:
		return []
	revenue = flt(tot.get("revenue"))
	gross_profit = flt(tot.get("gross_profit"))
	margin = (gross_profit / revenue * 100) if revenue else 0
	item_codes = set(r.get("item_code") for r in body)
	summary = [
		{"label": _("Sales Amount"), "value": revenue, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("COGS"), "value": flt(tot.get("cogs")), "datatype": "Currency", "indicator": "Orange"},
		{"label": _("Gross Profit"), "value": gross_profit, "datatype": "Currency",
			"indicator": "Green" if gross_profit >= 0 else "Red"},
		{"label": _("Margin %"), "value": margin, "datatype": "Percent",
			"indicator": "Green" if margin >= 0 else "Red"},
		{"label": _("Sold Qty"), "value": flt(tot.get("sold_qty")), "datatype": "Float"},
		{"label": _("Items"), "value": len(item_codes), "datatype": "Int", "indicator": "Blue"},
	]
	if flt(tot.get("purchase_amount")):
		summary.append({"label": _("Purchase Amount"), "value": flt(tot.get("purchase_amount")),
			"datatype": "Currency", "indicator": "Purple"})
	return summary


def build_chart(view, data):
	body = [r for r in data if (r.get("item_code") != "Total") and not r.get("bold")]
	if not body:
		return None

	if view == "Item - Monthly":
		# Gross profit trend per month (summed across items)
		buckets = {}
		for r in body:
			m = r.get("month") or ""
			buckets[m] = buckets.get(m, 0) + flt(r.get("gross_profit"))
		labels = sorted(buckets.keys())
		values = [round(buckets[m], 2) for m in labels]
		return {
			"data": {"labels": labels,
				"datasets": [{"name": _("Gross Profit"), "values": values}]},
			"type": "line", "colors": ["#1e7e34"],
			"lineOptions": {"regionFill": 1},
		}

	# Item Summary / Transaction -> top 10 items by gross profit
	agg = {}
	for r in body:
		code = r.get("item_code")
		if code not in agg:
			agg[code] = {"name": (r.get("item_name") or code), "gp": 0, "rev": 0}
		agg[code]["gp"] += flt(r.get("gross_profit"))
		agg[code]["rev"] += flt(r.get("revenue"))
	top = sorted(agg.values(), key=lambda x: x["gp"], reverse=True)[:10]
	labels = [(x["name"][:22]) for x in top]
	return {
		"data": {"labels": labels, "datasets": [
			{"name": _("Gross Profit"), "values": [round(x["gp"], 2) for x in top]},
			{"name": _("Sales Amount"), "values": [round(x["rev"], 2) for x in top]},
		]},
		"type": "bar", "colors": ["#1e7e34", "#5e64ff"],
		"barOptions": {"stacked": 0},
	}
