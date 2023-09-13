# Copyright (c) 2023, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _
def get_columns(filters):
	columns = [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Data" },
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Date" },

	]
	if not filters.get("update_stock"):
		columns += [
			{"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Data", "width": 180},
			{"label": _("Delivery Note Date"), "fieldname": "delivery_note_date", "fieldtype": "Date"},
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
		{"label": _("Gross Profit Percent"), "fieldname": "gross_profit_percent", "fieldtype": "Data"}
	]
	return columns
def get_conditions(filters):
	conditions = ""

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " and SI.posting_date BETWEEN '{0}' and '{1}'".format(filters.get("from_date"), filters.get("to_date"))

	if filters.get("customer"):
		conditions += " and SI.customer='{0}'".format(filters.get("customer"))

	if filters.get("sales_invoice"):
		conditions += " and SI.name='{0}'".format(filters.get("sales_invoice"))

	if filters.get("update_stock"):
		conditions += " and SI.update_stock='{0}'".format(filters.get("update_stock"))
	return conditions

def execute(filters=None):
	columns, data = get_columns(filters), []
	conditions = get_conditions(filters)
	sales_invoice = frappe.db.sql(""" SELECT 
  								SI.name as sales_invoice,
  								SI.posting_date as sales_invoice_date,
  								SI.customer,
  								SI.total_qty as si_qty,
  								SI.grand_total as selling_amount
							FROM `tabSales Invoice` SI
							WHERE SI.docstatus=1 {0}
							ORDER BY SI.name ASC
						""".format(conditions),as_dict=1)
	sales_invoice_items = frappe.db.sql(""" SELECT * FROm `tabSales Invoice Item`""",as_dict=1)
	delivery_note_items = frappe.db.sql(""" SELECT DNI.*, DN.posting_date FROM `tabDelivery Note`  DN 
 											INNER JOIN `tabDelivery Note Item` DNI ON DNI.parent = DN.name
 											""",as_dict=1)

	stock_ledger_entry = frappe.db.sql(""" SELECT * FROM `tabStock Ledger Entry` WHERE is_cancelled=0""",as_dict=1)
	data = []
	totals = {
		"sales_invoice": "Total",
		"si_qty": 0,
		"selling_amount": 0,
		"cogs": 0,
		"gross_profit": 0,
		'bold': True
	}
	for idx,x in enumerate(sales_invoice):
		data.append(x)
		sii,total,gross_profit,dn_name,dn_date = get_sales_invoice_items(x, sales_invoice_items,stock_ledger_entry,filters,delivery_note_items)

		x['cogs'] = total
		x['gross_profit'] = gross_profit
		x['gross_profit_percent'] = str(round(gross_profit / x.selling_amount * 100,2)) + "%"
		x['bold'] = True
		x['delivery_note'] = dn_name
		x['delivery_note_date'] = dn_date
		totals['si_qty'] += x['si_qty']
		totals['selling_amount'] += x['selling_amount']
		totals['cogs'] += x['cogs']
		totals['gross_profit'] += x['gross_profit']
		if len(sii) > 0:
			for xxx in sii:
				objj = {
					"item_code": xxx.item_code,
					"item_name": xxx.item_name,
					"si_qty": xxx.qty,
					"warehouse": xxx.warehouse,
					"cogs": xxx['cogs'] * xxx.qty,
					"selling_amount": xxx.amount,
					"gross_profit": xxx.amount - (xxx['cogs'] * xxx.qty),
					"gross_profit_percent": str(round((( xxx.amount - (xxx['cogs'] * xxx.qty)) / xxx.amount) * 100,2)) + "%",
					"parent_dn": dn_name
				}
				if not filters.get("update_stock"):
					objj['dn_qty'] = xxx['dn_qty']

				data.append(objj)
	if totals['selling_amount'] > 0:
		totals['gross_profit_percent'] = str(round(totals['gross_profit'] / totals['selling_amount'] * 100,2)) + "%"
	data.append(totals)
	print(data)
	if not filters.get("update_stock") and filters.get("delivery_note"):
		data = [x for x in data if (x.get('delivery_note') and filters.get("delivery_note") == x.get('delivery_note')) or (x.get("parent_dn") and x.get("parent_dn") == filters.get("delivery_note"))]
	return columns, data

def get_sales_invoice_items(x, sales_invoice_items,stock_ledger_entry,filters,delivery_note_items):
	items = []
	total = 0
	gross_profit = 0
	dn_name = ""
	dn_date = ""
	print("=============================")
	for xx in sales_invoice_items:
		if x.sales_invoice == xx.parent:
			xx['cogs'] = get_cogs(stock_ledger_entry,xx)
			total +=  (xx['cogs'] * xx.qty)
			gross_profit += round(xx.amount - (xx['cogs'] * xx.qty),2)
			if not filters.get("update_stock"):
				xx['dn_qty'],dn_name,dn_date = get_dn_details(xx,delivery_note_items)
			items.append(xx)
	return items,total,gross_profit,dn_name,dn_date

def get_cogs(stock_ledger_entry,xx):

	for x in stock_ledger_entry:
		if xx.name == x.voucher_detail_no:
			return x.incoming_rate
	return 0

def get_dn_details(xx,delivery_note_items):
	print("++++++++++++++++++++++++++++++++++++++++++++++")
	print(xx)
	print('dn_detail' not in xx or not xx['dn_detail'])
	if 'dn_detail' not in xx or not xx['dn_detail']:
		for x in delivery_note_items:
			if x.si_detail == xx.name:
				return x.qty,x.parent,x.posting_date
	else:
		print(xx['dn_detail'])
		for x in delivery_note_items:
			if x.name == xx.dn_detail:
				return x.qty,x.parent,x.posting_date
	return 0,"",""
