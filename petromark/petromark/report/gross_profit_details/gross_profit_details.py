# Copyright (c) 2023, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _
def get_columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Data" },
		{"label": _("Sales Invoice Date"), "fieldname": "sales_invoice_date", "fieldtype": "Date" },
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer"},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Data"},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data"},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data"},
		{"label": _("SI Qty"), "fieldname": "si_qty", "fieldtype": "Float"},
		{"label": _("Selling Amount"), "fieldname": "selling_amount", "fieldtype": "Currency"},
		{"label": _("COGS"), "fieldname": "cogs", "fieldtype": "Currency","width": 100},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Data"},
		{"label": _("Gross Profit Percent"), "fieldname": "gross_profit_percent", "fieldtype": "Data"}
	]
def execute(filters=None):
	columns, data = get_columns(), []

	sales_invoice = frappe.db.sql(""" SELECT 
  								SI.name as sales_invoice,
  								SI.posting_date as sales_invoice_date,
  								SI.customer,
  								SI.total_qty as si_qty,
  								SI.grand_total as selling_amount
							FROM `tabSales Invoice` SI
							WHERE SI.docstatus=1 and SI.update_stock=1
							ORDER BY SI.name ASC
						""",as_dict=1)
	sales_invoice_items = frappe.db.sql(""" SELECT * FROm `tabSales Invoice Item`""",as_dict=1)
	# delivery_notes = frappe.db.sql(""" SELECT
  	# 							SI.name as delivery_note,
  	# 							SI.posting_date,
  	# 							SII.item_code,
  	# 							SII.item_name,
  	# 							SII.qty as dn_qty,
  	# 							SII.name as dn_name,
  	# 							SII.parent
	# 						FROM `tabDelivery Note` SI
	# 						INNER JOIN `tabDelivery Note Item` SII ON SII.parent = SI.name
	# 						WHERE SI.docstatus=1
	# 						ORDER BY SI.name,SII.item_code ASC
	# 					""",as_dict=1)
	stock_ledger_entry = frappe.db.sql(""" SELECT * FROM `tabStock Ledger Entry` WHERE is_cancelled=0""",as_dict=1)
	data = []
	for idx,x in enumerate(sales_invoice):
		data.append(x)
		sii = get_sales_invoice_items(x, sales_invoice_items,stock_ledger_entry)
		if len(sii) > 0:
			for xxx in sii:
				data.append({
					"item_code": xxx.item_code,
					"item_name": xxx.item_name,
					"si_qty": xxx.qty,
					"warehouse": xxx.warehouse,
					"cogs": xxx['cogs'] * xxx.qty,
					"selling_amount": xxx.amount,
					"gross_profit": xxx.amount - (xxx['cogs'] * xxx.qty),
					"gross_profit_percent": (( xxx.amount - (xxx['cogs'] * xxx.qty)) / xxx.amount) * 100
				})
	return columns, data

def get_sales_invoice_items(x, sales_invoice_items,stock_ledger_entry):
	items = []
	for xx in sales_invoice_items:
		if x.sales_invoice == xx.parent:
			xx['cogs'] = get_cogs(stock_ledger_entry,xx)
			items.append(xx)
	return items

def get_cogs(stock_ledger_entry,xx):

	for x in stock_ledger_entry:
		if xx.name == x.voucher_detail_no:
			return x.incoming_rate
	return 0