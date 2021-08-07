// Copyright (c) 2016, sammish and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Statement of Account"] = {
	"filters": [
		{
			fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1
		},
		{
			fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
			reqd: 1

		},
		{
			fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
			reqd: 1,
			"on_change": function (txt) {
				var customer = frappe.query_report.get_filter('customer').value
				frappe.db.get_doc("Customer", customer).then((customer) => {
					frappe.query_report.set_filter_value("customer_name",customer.customer_name)
				})
            }
		},
		{
			fieldname: "customer_name",
            label: __("Customer Name"),
            fieldtype: "Data",
			hidden: 1,
		}

	]
};

