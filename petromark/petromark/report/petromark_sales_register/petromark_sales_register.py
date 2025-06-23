# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 120
		},
		{
			"label": _("Voucher"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 200
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 150
		},
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 150
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 250
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 100
		},
		{
			"label": _("Net Total"),
			"fieldname": "net_total",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Tax Total"),
			"fieldname": "total_taxes_and_charges",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Grand Total"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Rounded Total"),
			"fieldname": "rounded_total",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 180
		}
	]
	return columns


def get_data(filters):
	conditions = get_conditions(filters)
	
	data = frappe.db.sql("""
		SELECT 
			'Sales Invoice' as voucher_type,
			si.name as voucher_no,
			si.posting_date,
			'' as sales_person,
			si.customer,
			si.currency,
			IFNULL(si.net_total, 0) as net_total,
			IFNULL(si.total_taxes_and_charges, 0) as total_taxes_and_charges,
			IFNULL(si.grand_total, 0) as grand_total,
			IFNULL(si.rounded_total, 0) as rounded_total,
			IFNULL(si.outstanding_amount, 0) as outstanding_amount
		FROM 
			`tabSales Invoice` si
		WHERE 
			si.docstatus = 1
			{conditions}
		ORDER BY 
			si.posting_date DESC, si.name DESC
	""".format(conditions=conditions), filters, as_dict=1)
	
	# Try to get sales person data separately if it exists
	for row in data:
		try:
			sales_person_result = frappe.db.sql("""
				SELECT sales_person 
				FROM `tabSales Team` 
				WHERE parent = %s AND parenttype = 'Sales Invoice'
				LIMIT 1
			""", row.voucher_no)
			if sales_person_result and sales_person_result[0][0]:
				row.sales_person = sales_person_result[0][0]
			else:
				row.sales_person = ""
		except:
			row.sales_person = ""
	
	return data


def get_conditions(filters):
	conditions = ""
	
	if filters.get("from_date"):
		conditions += " AND si.posting_date >= %(from_date)s"
	
	if filters.get("to_date"):
		conditions += " AND si.posting_date <= %(to_date)s"
	
	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"
	
	if filters.get("company"):
		conditions += " AND si.company = %(company)s"
	
	# Handle sales person filter separately if needed
	if filters.get("sales_person"):
		conditions += """ AND si.name IN (
			SELECT parent FROM `tabSales Team` 
			WHERE sales_person = %(sales_person)s AND parenttype = 'Sales Invoice'
		)"""
	
	return conditions


def get_conditions_without_sales_person(filters):
	conditions = ""
	
	if filters.get("from_date"):
		conditions += " AND si.posting_date >= %(from_date)s"
	
	if filters.get("to_date"):
		conditions += " AND si.posting_date <= %(to_date)s"
	
	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"
	
	if filters.get("company"):
		conditions += " AND si.company = %(company)s"
	
	return conditions