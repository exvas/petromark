// Copyright (c) 2023, sammish and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Update Stock Check Report"] = {
	"filters": [
		{
			fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
		},
		{
			fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
		},
		{
			fieldname: "sales_invoice",
            label: __("Sales Invoice"),
            fieldtype: "Link",
            options: "Sales Invoice",
		},
	]
};