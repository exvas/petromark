# Copyright (c) 2026, sammish and contributors
# For license information, please see license.txt
"""Minimum gross margin protection for selling documents.

Entirely optional: controlled from Selling Settings. When
"Enable Minimum Margin Check" is off (the default) this module does
nothing at all.

Margin is measured on the selling price:

    minimum_rate = cost / (1 - margin% / 100)

Cost is the stock valuation rate of the row's warehouse, converted to the
row UOM. The selling side is ``base_net_rate`` - company currency, net of
taxes and of any distributed invoice level discount.
"""

import frappe
from frappe import _
from frappe.utils import flt

# Guards against blocking a sale because of a sub-cent rounding difference.
TOLERANCE = 0.000001


def get_settings():
	"""Return margin settings, or None when the feature is switched off."""
	s = frappe.get_cached_doc("Selling Settings")
	if not s.get("custom_enable_minimum_margin"):
		return None

	margin = flt(s.get("custom_minimum_margin_percent"))
	# A margin of 100% or more would demand an infinite selling rate.
	if margin >= 100:
		frappe.throw(
			_("Minimum Gross Margin (%) must be less than 100. Please correct Selling Settings."),
			title=_("Invalid Margin Setting"),
		)

	return frappe._dict({
		"margin": margin,
		"action": s.get("custom_margin_action") or "Warn",
		"bypass_role": s.get("custom_margin_bypass_role"),
		"block_missing_valuation": int(s.get("custom_block_missing_valuation") or 0),
	})


def validate_margin(doc, method=None):
	"""Check every stock row of the document against the minimum margin."""
	if doc.doctype not in ("Sales Invoice", "POS Invoice"):
		return

	# Returns reverse an earlier sale; opening entries carry no real cost.
	if doc.get("is_return") or doc.get("is_opening") == "Yes":
		return

	settings = get_settings()
	if not settings:
		return

	violations = []
	skipped_no_cost = []

	for row in doc.items:
		if not row.item_code or flt(row.qty) <= 0:
			continue

		# Free items are given away deliberately.
		if row.get("is_free_item"):
			continue

		item = frappe.get_cached_value(
			"Item", row.item_code, ["is_stock_item"], as_dict=True
		)
		# Only stock items have a valuation to measure margin against.
		if not item or not item.is_stock_item:
			continue

		if not row.warehouse:
			skipped_no_cost.append((row.idx, row.item_code, _("no warehouse")))
			continue

		valuation = frappe.db.get_value(
			"Bin",
			{"item_code": row.item_code, "warehouse": row.warehouse},
			"valuation_rate",
		)
		if not valuation or flt(valuation) <= 0:
			skipped_no_cost.append((row.idx, row.item_code, _("no stock valuation")))
			continue

		conversion = flt(row.conversion_factor) or 1.0
		# Valuation is per stock UOM; bring it onto the row's UOM.
		cost_per_unit = flt(valuation) * conversion
		minimum_rate = cost_per_unit / (1.0 - (settings.margin / 100.0))
		selling_rate = flt(row.base_net_rate)

		if selling_rate + TOLERANCE < minimum_rate:
			violations.append({
				"idx": row.idx,
				"item_code": row.item_code,
				"cost": cost_per_unit,
				"minimum": minimum_rate,
				"actual": selling_rate,
			})

	if skipped_no_cost and settings.block_missing_valuation:
		frappe.throw(
			_("Cost is unknown for these rows, so the margin cannot be checked:<br>{0}").format(
				"<br>".join(
					_("Row {0}: {1} ({2})").format(i, code, why)
					for i, code, why in skipped_no_cost
				)
			),
			title=_("Minimum Margin Violation"),
		)

	if not violations:
		return

	_report(doc, settings, violations)


def _report(doc, settings, violations):
	"""Raise or warn, and say exactly which rows are under the limit."""
	currency = doc.get("company_currency") or frappe.get_cached_value(
		"Company", doc.company, "default_currency"
	)

	lines = [
		_("Row {0} - {1}: cost {2}, minimum {3}, entered {4}").format(
			v["idx"],
			v["item_code"],
			frappe.format_value(v["cost"], {"fieldtype": "Currency", "options": "currency"}, doc),
			frappe.format_value(v["minimum"], {"fieldtype": "Currency", "options": "currency"}, doc),
			frappe.format_value(v["actual"], {"fieldtype": "Currency", "options": "currency"}, doc),
		)
		for v in violations
	]

	intro = _("These rows are below the minimum gross margin of {0}%. Rates are in {1}, per invoice UOM, excluding tax.").format(
		flt(settings.margin), currency
	)
	message = intro + "<br><br>" + "<br>".join(lines)

	# An invoice level discount is normally spread across the rows, so the
	# figures above already include it. A Grand Total cash/non-trade discount
	# is not spread, so the real margin is lower than shown.
	if (
		flt(doc.get("discount_amount"))
		and doc.get("apply_discount_on") == "Grand Total"
		and doc.get("is_cash_or_non_trade_discount")
	):
		message += "<br><br>" + _(
			"Note: this invoice has a Grand Total cash discount that is not spread across rows, "
			"so the real margin is lower than shown."
		)

	blocking = settings.action == "Block"
	if blocking and settings.bypass_role and settings.bypass_role in frappe.get_roles():
		blocking = False
		message += "<br><br>" + _("Allowed because you have the {0} role.").format(
			frappe.bold(settings.bypass_role)
		)

	if blocking:
		frappe.throw(message, title=_("Minimum Margin Violation"))
	else:
		frappe.msgprint(message, title=_("Below Minimum Margin"), indicator="orange")
