# -*- coding: utf-8 -*-
# Copyright (c) 2021, ifitwala and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from json import loads
from six import string_types

import frappe, ifitwala_ed
from frappe import _
import frappe.defaults
from frappe.utils import nowdate, cstr, flt, cint, now, getdate
from frappe.utils import formatdate, get_number_format_info, get_number_format_info
from frappe.model.meta import get_field_precision

# imported to enable ifitwala_ed.accounting.utils.get_account_currency
from ifitwala_ed.accounting.doctype.account.account import get_account_currency
from ifitwala_ed.stock import get_location_account_map
from ifitwala_ed.stock.utils import get_stock_value_on

class StockValueAndAccountBalanceOutOfSync(frappe.ValidationError): pass
class FiscalYearError(frappe.ValidationError): pass
class PaymentEntryUnlinkError(frappe.ValidationError): pass


@frappe.whitelist()
def get_fiscal_year(date=None, fiscal_year=None, label="Date", verbose=1, organization=None, as_dict=False):
	return get_fiscal_years(date, fiscal_year, label, verbose, organization, as_dict=as_dict)[0]

def get_fiscal_years(transaction_date=None, fiscal_year=None, label="Date", verbose=1, organization=None, as_dict=False):
	fiscal_years = frappe.cache().hget("fiscal_years", organization) or []

	if not fiscal_years:
		# if year start date is 2012-04-01, year end date should be 2013-03-31 (hence subdate)
		cond = ""
		if fiscal_year:
			cond += " and fy.name = {0}".format(frappe.db.escape(fiscal_year))
		if organization:
			cond += """
				AND (not exists (select name
					from `tabFiscal Year Organization` fyc
					where fyc.parent = fy.name)
				OR exists(select organization
					from `tabFiscal Year Organization` fyc
					where fyc.parent = fy.name
					and fyc.organization=%(organization)s)
				)
			"""

		fiscal_years = frappe.db.sql("""
			SELECT
				fy.name, fy.year_start_date, fy.year_end_date
			FROM
				`tabFiscal Year` fy
			WHERE
				disabled = 0 {0}
			ORDER BY
				fy.year_start_date desc""".format(cond), {
				"organization": organization
			}, as_dict=True)

		frappe.cache().hset("fiscal_years", organization, fiscal_years)

	if not transaction_date and not fiscal_year:
		return fiscal_years

	if transaction_date:
		transaction_date = getdate(transaction_date)

	for fy in fiscal_years:
		matched = False
		if fiscal_year and fy.name == fiscal_year:
			matched = True

		if (transaction_date and getdate(fy.year_start_date) <= transaction_date
			and getdate(fy.year_end_date) >= transaction_date):
			matched = True

		if matched:
			if as_dict:
				return (fy,)
			else:
				return ((fy.name, fy.year_start_date, fy.year_end_date),)

	error_msg = _("""{0} {1} is not in any active Fiscal Year""").format(label, formatdate(transaction_date))
	if organization:
		error_msg = _("""{0} for {1}""").format(error_msg, frappe.bold(organization))

	if verbose==1: frappe.msgprint(error_msg)
	raise FiscalYearError(error_msg)

@frappe.whitelist()
def get_fiscal_year_filter_field(organization=None):
	field = {
		"fieldtype": "Select",
		"options": [],
		"operator": "Between",
		"query_value": True
	}
	fiscal_years = get_fiscal_years(organization=organization)
	for fiscal_year in fiscal_years:
		field["options"].append({
			"label": fiscal_year.name,
			"value": fiscal_year.name,
			"query_value": [fiscal_year.year_start_date.strftime("%Y-%m-%d"), fiscal_year.year_end_date.strftime("%Y-%m-%d")]
		})
	return field

def validate_field_number(doctype_name, docname, number_value, organization, field_name):
	''' Validate if the number entered isn't already assigned to some other document. '''
	if number_value:
		filters = {field_name: number_value, "name": ["!=", docname]}
		if organization:
			filters["organization"] = organization

		doctype_with_same_number = frappe.db.get_value(doctype_name, filters)

		if doctype_with_same_number:
			frappe.throw(_("{0} Number {1} is already used in {2} {3}").format(doctype_name, number_value, doctype_name.lower(), doctype_with_same_number))

def get_autoname_with_number(number_value, doc_title, name, organization):
	''' append title with prefix as number and suffix as organization's abbreviation separated by '-' '''
	if name:
		name_split=name.split("-")
		parts = [doc_title.strip(), name_split[len(name_split)-1].strip()]
	else:
		abbr = frappe.get_cached_value('Organization',  organization,  ["abbr"], as_dict=True)
		parts = [doc_title.strip(), abbr.abbr]
	if cstr(number_value).strip():
		parts.insert(0, cstr(number_value).strip())
	return ' - '.join(parts)

@frappe.whitelist()
def get_balance_on(account=None, date=None, party_type=None, party=None, organization=None, in_account_currency=True, cost_center=None, ignore_account_permission=False):
	if not account and frappe.form_dict.get("account"):
		account = frappe.form_dict.get("account")
	if not date and frappe.form_dict.get("date"):
		date = frappe.form_dict.get("date")
	if not party_type and frappe.form_dict.get("party_type"):
		party_type = frappe.form_dict.get("party_type")
	if not party and frappe.form_dict.get("party"):
		party = frappe.form_dict.get("party")
	if not cost_center and frappe.form_dict.get("cost_center"):
		cost_center = frappe.form_dict.get("cost_center")

	cond = ["is_cancelled=0"]
	if date:
		cond.append("posting_date <= %s" % frappe.db.escape(cstr(date)))
	else:
		# get balance of all entries that exist
		date = nowdate()

	if account:
		acc = frappe.get_doc("Account", account)

	try:
		year_start_date = get_fiscal_year(date, organization=organization, verbose=0)[1]
	except FiscalYearError:
		if getdate(date) > getdate(nowdate()):
			# if fiscal year not found and the date is greater than today
			# get fiscal year for today's date and its corresponding year start date
			year_start_date = get_fiscal_year(nowdate(), verbose=1)[1]
		else:
			# this indicates that it is a date older than any existing fiscal year.
			# hence, assuming balance as 0.0
			return 0.0

	if account:
		report_type = acc.report_type
	else:
		report_type = ""

	if cost_center and report_type == 'Profit and Loss':
		cc = frappe.get_doc("Cost Center", cost_center)
		if cc.is_group:
			cond.append(""" exists (
				select 1 from `tabCost Center` cc where cc.name = gle.cost_center
				and cc.lft >= %s and cc.rgt <= %s
			)""" % (cc.lft, cc.rgt))

		else:
			cond.append("""gle.cost_center = %s """ % (frappe.db.escape(cost_center, percent=False), ))


	if account:

		if not (frappe.flags.ignore_account_permission
			or ignore_account_permission):
			acc.check_permission("read")

		if report_type == 'Profit and Loss':
			# for pl accounts, get balance within a fiscal year
			cond.append("posting_date >= '%s' and voucher_type != 'Period Closing Voucher'" % year_start_date)
		# different filter for group and ledger - improved performance
		if acc.is_group:
			cond.append("""exists (
				select name from `tabAccount` ac where ac.name = gle.account
				and ac.lft >= %s and ac.rgt <= %s
			)""" % (acc.lft, acc.rgt))

			# If group and currency same as organization,
			# always return balance based on debit and credit in organization currency
			if acc.account_currency == frappe.get_cached_value('Organization',  acc.organization,  "default_currency"):
				in_account_currency = False
		else:
			cond.append("""gle.account = %s """ % (frappe.db.escape(account, percent=False), ))

	if party_type and party:
		cond.append("""gle.party_type = %s and gle.party = %s """ %
			(frappe.db.escape(party_type), frappe.db.escape(party, percent=False)))

	if organization:
		cond.append("""gle.organization = %s """ % (frappe.db.escape(organization, percent=False)))

	if account or (party_type and party):
		if in_account_currency:
			select_field = "sum(debit_in_account_currency) - sum(credit_in_account_currency)"
		else:
			select_field = "sum(debit) - sum(credit)"
		bal = frappe.db.sql("""
			SELECT {0}
			FROM `tabGL Entry` gle
			WHERE {1}""".format(select_field, " and ".join(cond)))[0][0]

		# if bal is None, return 0
		return flt(bal)

def get_count_on(account, fieldname, date):
	cond = ["is_cancelled=0"]
	if date:
		cond.append("posting_date <= %s" % frappe.db.escape(cstr(date)))
	else:
		# get balance of all entries that exist
		date = nowdate()

	try:
		year_start_date = get_fiscal_year(date, verbose=0)[1]
	except FiscalYearError:
		if getdate(date) > getdate(nowdate()):
			# if fiscal year not found and the date is greater than today
			# get fiscal year for today's date and its corresponding year start date
			year_start_date = get_fiscal_year(nowdate(), verbose=1)[1]
		else:
			# this indicates that it is a date older than any existing fiscal year.
			# hence, assuming balance as 0.0
			return 0.0

	if account:
		acc = frappe.get_doc("Account", account)

		if not frappe.flags.ignore_account_permission:
			acc.check_permission("read")

		# for pl accounts, get balance within a fiscal year
		if acc.report_type == 'Profit and Loss':
			cond.append("posting_date >= '%s' and voucher_type != 'Period Closing Voucher'" \
				% year_start_date)

		# different filter for group and ledger - improved performance
		if acc.is_group:
			cond.append("""exists (
				select name from `tabAccount` ac where ac.name = gle.account
				and ac.lft >= %s and ac.rgt <= %s
			)""" % (acc.lft, acc.rgt))
		else:
			cond.append("""gle.account = %s """ % (frappe.db.escape(account, percent=False), ))

		entries = frappe.db.sql("""
			SELECT name, posting_date, account, party_type, party,debit,credit,
				voucher_type, voucher_no, against_voucher_type, against_voucher
			FROM `tabGL Entry` gle
			WHERE {0}""".format(" and ".join(cond)), as_dict=True)

		count = 0
		for gle in entries:
			if fieldname not in ('invoiced_amount','payables'):
				count += 1
			else:
				dr_or_cr = "debit" if fieldname == "invoiced_amount" else "credit"
				cr_or_dr = "credit" if fieldname == "invoiced_amount" else "debit"
				select_fields = "ifnull(sum(credit-debit),0)" \
					if fieldname == "invoiced_amount" else "ifnull(sum(debit-credit),0)"

				if ((not gle.against_voucher) or (gle.against_voucher_type in ["Sales Order", "Purchase Order"]) or
				(gle.against_voucher==gle.voucher_no and gle.get(dr_or_cr) > 0)):
					payment_amount = frappe.db.sql("""
						SELECT {0}
						FROM `tabGL Entry` gle
						WHERE docstatus < 2 and posting_date <= %(date)s and against_voucher = %(voucher_no)s
						and party = %(party)s and name != %(name)s"""
						.format(select_fields),
						{"date": date, "voucher_no": gle.voucher_no,
							"party": gle.party, "name": gle.name})[0][0]

					outstanding_amount = flt(gle.get(dr_or_cr)) - flt(gle.get(cr_or_dr)) - payment_amount
					currency_precision = get_currency_precision() or 2
					if abs(flt(outstanding_amount)) > 0.1/10**currency_precision:
						count += 1

		return count

def get_currency_precision():
	precision = cint(frappe.db.get_default("currency_precision"))
	if not precision:
		number_format = frappe.db.get_default("number_format") or "#,###.##"
		precision = get_number_format_info(number_format)[2]

	return precision

@frappe.whitelist()
def add_ac(args=None):
	from frappe.desk.treeview import make_tree_args

	if not args:
		args = frappe.local.form_dict

	args.doctype = "Account"
	args = make_tree_args(**args)

	ac = frappe.new_doc("Account")

	if args.get("ignore_permissions"):
		ac.flags.ignore_permissions = True
		args.pop("ignore_permissions")

	ac.update(args)

	if not ac.parent_account:
		ac.parent_account = args.get("parent")

	ac.old_parent = ""
	ac.freeze_account = "No"
	if cint(ac.get("is_root")):
		ac.parent_account = None
		ac.flags.ignore_mandatory = True

	ac.insert()

	return ac.name

@frappe.whitelist()
def get_children(doctype, parent, organization, is_root=False):
	from ifitwala_ed.accounting.report.financial_statements import sort_accounts

	parent_fieldname = 'parent_' + doctype.lower().replace(' ', '_')
	fields = [
		'name as value',
		'is_group as expandable'
	]
	filters = [['docstatus', '<', 2]]

	filters.append(['ifnull(`{0}`,"")'.format(parent_fieldname), '=', '' if is_root else parent])

	if is_root:
		fields += ['root_type', 'report_type', 'account_currency'] if doctype == 'Account' else []
		filters.append(['organization', '=', organization])

	else:
		fields += ['root_type', 'account_currency'] if doctype == 'Account' else []
		fields += [parent_fieldname + ' as parent']

	acc = frappe.get_list(doctype, fields=fields, filters=filters)

	if doctype == 'Account':
		sort_accounts(acc, is_root, key="value")

	return acc

@frappe.whitelist()
def get_account_balances(accounts, organization):

	if isinstance(accounts, string_types):
		accounts = loads(accounts)

	if not accounts:
		return []

	organization_currency = frappe.get_cached_value("Organization",  organization,  "default_currency")

	for account in accounts:
		account["organization_currency"] = organization_currency
		account["balance"] = flt(get_balance_on(account["value"], in_account_currency=False, organization=organization))
		if account["account_currency"] and account["account_currency"] != organization_currency:
			account["balance_in_account_currency"] = flt(get_balance_on(account["value"], organization=organization))

	return accounts

@frappe.whitelist()
def get_coa(doctype, parent, is_root, chart=None):
	from ifitwala_ed.accounting.doctype.account.chart_of_accounts.chart_of_accounts import build_tree_from_json

	# add chart to flags to retrieve when called from expand all function
	chart = chart if chart else frappe.flags.chart
	frappe.flags.chart = chart

	parent = None if parent==_('All Accounts') else parent
	accounts = build_tree_from_json(chart) # returns alist of dict in a tree render-able form

	# filter out to show data for the selected node only
	accounts = [d for d in accounts if d['parent_account']==parent]

	return accounts

def validate_fiscal_year(date, fiscal_year, organization, label="Date", doc=None):
	years = [f[0] for f in get_fiscal_years(date, label=_(label), organization=organization)]
	if fiscal_year not in years:
		if doc:
			doc.fiscal_year = years[0]
		else:
			throw(_("{0} '{1}' not in Fiscal Year {2}").format(label, formatdate(date), fiscal_year))
