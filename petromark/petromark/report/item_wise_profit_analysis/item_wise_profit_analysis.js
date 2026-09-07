// Copyright (c) 2026, sammish and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Item Wise Profit Analysis"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
			"reqd": 1,
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname": "view_type",
			"label": __("View By"),
			"fieldtype": "Select",
			"options": "Item Summary\nItem - Monthly\nTransaction",
			"default": "Item Summary",
		},
		{
			"fieldname": "sort_by",
			"label": __("Sort By (Summary)"),
			"fieldtype": "Select",
			"options": "Gross Profit\nSales Amount\nSold Qty\nMargin %",
			"default": "Gross Profit",
		},
		{
			"fieldname": "show_purchase_stock",
			"label": __("Show Purchase & Stock"),
			"fieldtype": "Check",
			"default": 1,
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
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
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.bold) {
			value = $(`<span>${value}</span>`).css("font-weight", "bold").wrap("<p></p>").parent().html();
		}

		// Colour profit / margin: green when positive, red when negative.
		if (data && ["gross_profit", "margin_pct"].includes(column.fieldname)) {
			let v = flt(data[column.fieldname]);
			if (v < 0) {
				value = `<span style="color:#c0392b">${value}</span>`;
			} else if (v > 0) {
				value = `<span style="color:#1e7e34">${value}</span>`;
			}
		}
		return value;
	},
};
