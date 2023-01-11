# Copyright (c) 2023, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint
def execute(filters=None):
	columns, data = [], []
	columns=get_columns()
	conditions=get_conditions(filters)
	lists=get_lists(filters)
	for li in lists:
		row=frappe._dict({
				'date':li.date,
				'customer':li.customer,
				'sales_invoice_reference':li.sales_invoice_reference,
				'reference':li.reference,
				'grand_total':li.grand_total,
				'outstanding_amount':li.outstanding_amount,
				'paid_amount':li.paid_amount,
			})	
		data.append(row)
		if li.status=="Paid":
			si_name=li.get('sales_invoice_reference')
			pay_lists=get_pay_lists(filters,si_name)
			for l in pay_lists:
				row=frappe._dict({
					'date':l.date,
					'customer':l.customer,
					'sales_invoice_reference':l.sales_invoice_reference,
					'reference':l.pname,
					'grand_total':l.grand_total,
					'outstanding_amount':l.outstanding_amount,
					'paid_amount':l.paid_amount,
					
					
				})
				
			
				data.append(row)

	other_date_payment_list=get_payment_list(filters)
	for l in other_date_payment_list:
		row=frappe._dict({
			'date':l.date,
			'customer':l.customer,
			'sales_invoice_reference':l.sales_invoice_reference,
			'reference':l.pname,
			'grand_total':l.grand_total,
			'outstanding_amount':l.outstanding_amount,
			'paid_amount':l.paid_amount,
			
			
		})
		data.append(row)
	return columns,data

def get_columns():
	return[
		{
			"fieldname": "date",
   			"fieldtype": "Date",
   			"label": "Date",	
				

		},
		{
   			"fieldname": "customer",
   			"fieldtype": "Link",
   			"label": "Customer Name",
			"options":"Customer",
			"width":170
			
 		},
		{
   			"fieldname": "sales_invoice_reference",
   			"fieldtype": "Link",
   			"label": "SI Reference",
			"options":"Sales Invoice",
			"width":150
  		},
		{
   			"fieldname": "reference",
   			"fieldtype": "Link",
   			"label": "PE Reference",
			"options":"Payment Entry",
			"width":170
  		},
		{
   			"fieldname": "grand_total",
   			"fieldtype": "Currency",
   			"label": "Grand Total",
			"width":120 
  		},
  		{
   			"fieldname": "outstanding_amount",
   			"fieldtype": "Currency",
   			"label": "Outstanding Amount",
			"width":120 
  		},
		{
   			"fieldname": "paid_amount",
   			"fieldtype": "Currency",
   			"label": "Paid Amount",
			"width":120 
  		},	
	]
def get_lists(filters):
	
	conditions=get_conditions(filters)
	data=[]

	parent=frappe.db.sql("""SELECT pe.posting_date as date,pe.company,pe.name as 
	sales_invoice_reference,pe.grand_total,pe.outstanding_amount,pe.paid_amount,pe.status,pe.customer_name as customer,st1.sales_person 
	FROM `tabSales Invoice` AS pe INNER JOIN `tabSales Team` AS st1 ON pe.name=st1.parent where 
	pe.docstatus=1 {0} """.format(conditions),as_dict=1)
	for dic_p in parent:
		dic_p["indent"] = 0
		filters=conditions
		data.append(dic_p)
		
	return data
def get_pay_lists(filters,si_name):
	conditions=get_conditions(filters)
	data=[]
	parent= frappe.db.sql("""SELECT pe.posting_date as date,
	pe.name as pname,
	pe.company,
	pe.party_name as customer,
	pe.sales_person,
	pe.total_allocated_amount as paid_amount
	FROM `tabPayment Entry` AS pe INNER JOIN `tabPayment Entry Reference` AS p
	ON p.parent=pe.name WHERE p.reference_name=%s {0}""".format(conditions),si_name,as_dict=1)
	for dic_p in parent:
		dic_p["indent"] = 0
		filters=conditions
		data.append(dic_p)
	return data

def get_payment_list(filters):
	conditions=get_conditions(filters)
	data=[]
	parent=frappe.db.sql("""select 
	pe.posting_date as date,
	pe.company,
	pe.sales_person,
	pe.party_name as customer,
	pe.total_allocated_amount as paid_amount,
	pe.name as pname,
	p.reference_name as sales_invoice_reference,
	p.reference_doctype,
	s.posting_date,
	s.name 
	from `tabPayment Entry` as pe inner join `tabPayment Entry Reference` as p on pe.name=p.parent 
	inner join `tabSales Invoice` as s on p.reference_name=s.name where p.reference_doctype='Sales Invoice' and
	pe.posting_date!=s.posting_date {0}""".format(conditions),as_dict=1)
	for dic_p in parent:
		dic_p["indent"] = 0
		filters=conditions
		data.append(dic_p)
	return data
def get_conditions(filters):
	conditions=""
	if filters.get("from_date") and filters.get("to_date"):
		conditions = "and pe.posting_date BETWEEN '{0}' and '{1}' ".format(filters.get("from_date"),filters.get("to_date"))
		if filters.get("company"):
			conditions += "and pe.company='{0}' ".format(filters.get("company"))
		if filters.get("sales_person"):
			conditions += "and sales_person='{0}' ".format(filters.get("sales_person"))
	if filters.get("company"):
			conditions += "and pe.company='{0}' ".format(filters.get("company"))
	if filters.get("sales_person"):
		conditions += "and sales_person='{0}' ".format(filters.get("sales_person"))
		
	# print(filters.get('from_date') , filters.get('to_date'))
		

	return conditions