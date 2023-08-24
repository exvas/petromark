// Copyright (c) 2023, sammish and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Gross Profit Details"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname":"customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},{
			"fieldname":"sales_invoice",
			"label": __("Sales Invoice"),
			"fieldtype": "Link",
			"options": "Sales Invoice"
		},{
			"fieldname":"delivery_note",
			"label": __("Delivery Note"),
			"fieldtype": "Link",
			"options": "Delivery Note"
		},
	],
};
