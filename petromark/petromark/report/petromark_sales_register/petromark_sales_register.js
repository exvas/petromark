// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Petromark Sales Register"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1,
			"width": "80px"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "80px"
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": "100px"
		},
		{
			"fieldname": "sales_person",
			"label": __("Sales Person"),
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": "100px"
		}
	],
	
	"formatter": function (value, row, column, data, default_formatter) {
		// Apply default formatting
		value = default_formatter(value, row, column, data);
		
		// Format currency fields
		if (column.fieldtype === "Currency" && value && !isNaN(value)) {
			value = format_currency(value, data.currency || "INR");
		}
		
		return value;
	},
	
	"onload": function(report) {
		// Add custom buttons or actions here if needed
		report.page.add_inner_button(__("Export"), function() {
			frappe.query_reports["Petromark Sales Register"].export_report();
		});
	},
	
	"export_report": function() {
		let filters = frappe.query_report.get_filter_values();
		let url = frappe.urllib.get_full_url(
			"/api/method/frappe.desk.query_report.export_query"
		);
		
		let args = {
			report_name: "Petromark Sales Register",
			file_format_type: "Excel",
			filters: JSON.stringify(filters)
		};
		
		open_url_post(url, args);
	},
	
	"get_datatable_options": function(options) {
		return Object.assign(options, {
			checkboxColumn: true,
			events: {
				onCheckRow: function(data) {
					// Custom row selection logic if needed
				}
			}
		});
	}
};