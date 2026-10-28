from . import __version__ as app_version

app_name = "petromark"
app_title = "Petromark"
app_publisher = "sammish"
app_description = "Petromark Qatar"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "sammish.thundiyil@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/petromark/css/petromark.css"
# app_include_js = "/assets/petromark/js/petromark.js"

# include js, css files in header of web template
# web_include_css = "/assets/petromark/css/petromark.css"
# web_include_js = "/assets/petromark/js/petromark.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "petromark/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "petromark.install.before_install"
# after_install = "petromark.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "petromark.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Payment Entry": {
        "before_insert": "petromark.petromark.events.payment_entry.set_sales_person_from_invoice"
    },
    "Sales Invoice": {
        "validate": "petromark.petromark.events.sales_invoice.validate_margin"
    },
    "POS Invoice": {
        "validate": "petromark.petromark.events.sales_invoice.validate_margin"
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"petromark.tasks.all"
# 	],
# 	"daily": [
# 		"petromark.tasks.daily"
# 	],
# 	"hourly": [
# 		"petromark.tasks.hourly"
# 	],
# 	"weekly": [
# 		"petromark.tasks.weekly"
# 	]
# 	"monthly": [
# 		"petromark.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "petromark.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "petromark.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "petromark.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]
# Export Fixtures
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "Payment Entry-sales_person",
					"Sales Invoice-ref_no",
					"Material Request-salesman",
					"Item-oem_part_number",
					"Sales Invoice Item-item_last_purchase_rate",
					"Sales Invoice Item-item_purchase_rate",
					"Sales Invoice Item-item_valuation_rate",
					"Sales Invoice Item-last_customer_rate",
					"Sales Invoice Item-item_last_rates",
					"Sales Invoice Item-column_break_100",
					"POS Profile-display_oem_part_number",
					"Selling Settings-custom_margin_protection_sb",
					"Selling Settings-custom_enable_minimum_margin",
					"Selling Settings-custom_minimum_margin_percent",
					"Selling Settings-custom_margin_action",
					"Selling Settings-custom_margin_cb",
					"Selling Settings-custom_margin_bypass_role",
					"Selling Settings-custom_block_missing_valuation"
                ]
            ]
        ]
    },
    {
        # Sales Invoice item grid: enter price in Price List Rate, discount in
        # Discount Amount -> Rate/Amount are the computed net.
        # Layout: Item(3) Qty(2) Price List Rate(2) Discount Amount(1) Amount(2)
        "doctype": "Property Setter",
        "filters": [
            [
                "doc_type",
                "=",
                "Sales Invoice Item"
            ],
            [
                "field_name",
                "in",
                [
                    "item_code",
                    "qty",
                    "price_list_rate",
                    "discount_amount",
                    "rate",
                    "amount"
                ]
            ]
        ]
    }
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"petromark.auth.validate"
# ]

