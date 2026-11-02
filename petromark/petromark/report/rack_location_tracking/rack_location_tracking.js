// Copyright (c) 2026, sammish and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Rack Location Tracking"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1,
		},
		{
			"fieldname": "view_type",
			"label": __("View"),
			"fieldtype": "Select",
			"options": "Current Rack by Item\nReceipt History\nRack Occupancy",
			"default": "Current Rack by Item",
			"reqd": 1,
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "All\nNeeds Attention\nOK\nMismatch\nNot in Master\nNo Rack",
			"default": "All",
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"get_query": function () {
				return {
					filters: { company: frappe.query_report.get_filter_value("company") },
				};
			},
		},
		{
			"fieldname": "rack_id",
			"label": __("Rack"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group",
		},
		{
			"fieldname": "brand",
			"label": __("Brand"),
			"fieldtype": "Link",
			"options": "Brand",
		},
		{
			"fieldname": "purchase_receipt",
			"label": __("Purchase Receipt"),
			"fieldtype": "Link",
			"options": "Purchase Receipt",
		},
		{
			"fieldname": "supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"fieldname": "pos_profile",
			"label": __("POS Profile"),
			"fieldtype": "Link",
			"options": "POS Profile",
		},
		{
			"fieldname": "show_zero_stock",
			"label": __("Show Zero Stock"),
			"fieldtype": "Check",
			"default": 0,
		},
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		if (column.fieldname === "status") {
			const colours = {
				"Mismatch": "red",
				"Not in Master": "orange",
				"No Rack": "orange",
				"OK": "green",
			};
			const colour = colours[data.status];
			if (colour) {
				value = `<span style="color:var(--text-on-${colour}, inherit);
					background-color:var(--bg-${colour});
					padding:1px 6px;border-radius:8px;">${data.status}</span>`;
			}
		}

		// the rack that is actually in force, so it reads as the answer
		if (column.fieldname === "current_rack" && data.current_rack) {
			value = `<b>${data.current_rack}</b>`;
		}

		// a receipt rack that the master does not agree with
		if (
			column.fieldname === "master_rack" &&
			data.status === "Mismatch" &&
			data.master_rack
		) {
			value = `<span style="color:var(--text-muted);text-decoration:line-through;">${data.master_rack}</span>`;
		}

		if (column.fieldname === "mismatch_count" && cint(data.mismatch_count) > 0) {
			value = `<span style="color:var(--text-on-orange);background-color:var(--bg-orange);
				padding:1px 6px;border-radius:8px;">${data.mismatch_count}</span>`;
		}

		return value;
	},

	"onload": function (report) {
		report.page.add_inner_button(__("Needs Attention"), function () {
			frappe.query_report.set_filter_value("status", "Needs Attention");
		});
		report.page.add_inner_button(__("Receipt History"), function () {
			frappe.query_report.set_filter_value("view_type", "Receipt History");
		});
		report.page.add_inner_button(__("Rack Occupancy"), function () {
			frappe.query_report.set_filter_value("view_type", "Rack Occupancy");
		});
	},
};
