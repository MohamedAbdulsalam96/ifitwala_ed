# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version
from frappe import _

app_name = "ifitwala_ed"
app_title = "Ifitwala ed"
app_publisher = "ifitwala"
app_description = "manage student data"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "f.deryckel@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_js = "ifitwala_ed.bundle.js"
app_include_css = "ifitwala_ed.bundle.css"

# include js, css files in header of web template
web_include_css = "ifitwala_ed-web.bundle.css"
web_include_js = "ifitwala_ed-web.bundle.js"

# setup wizard
#setup_wizard_requires = "assets/ifitwala_ed/js/setup_wizard.js"
#setup_wizard_stages = "ifitwala_ed.setup.setup_wizard.setup_wizard.get_setup_stages"
#before_install = "ifitwala_ed.setup.install.check_setup_wizard_not_completed"
after_install = "ifitwala_ed.setup.setup.setup_education"

filters_config = "ifitwala_ed.startup.filters.get_filters_config"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
	"Contact": "public/js/contact.js"
}
doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

update_website_context = ["ifitwala_ed.school_settings.doctype.education_settings.education_settings.update_website_context"]

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "ifitwala_ed.utils.get_home_page"

standard_portal_menu_items = [
	{"title": _("Personal Details"), "route": "/personal-details", "reference_doctype": "Student", "role": "Student"},
	{"title": _("Addresses"), "route": "/addresses", "reference_doctype": "Address"}
]

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "ifitwala_ed.install.before_install"
#after_install = "ifitwala_ed.setup.setup.setup_education"


calendars = ["School Event", "Course Schedule", "School Calendar", "Organization Event"]
# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ifitwala_ed.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Meeting": "ifitwala_ed.school_settings.doctype.meeting.meeting.get_permission_query_conditions",
    "School Event": "ifitwala_ed.school_settings.doctype.school_event.school_event.get_permission_query_conditions",
    "Student Group": "ifitwala_ed.schedule.doctype.student_group.student_group.get_permission_query_conditions",
	"Team": "ifitwala_ed.school_settings.doctype.team.team.get_permission_query_conditions",
	"Course Schedule": "ifitwala_ed.schedule.doctype.course_schedule.course_schedule.get_permission_query_conditions"
}
#
has_permission = {
    "Meeting": "ifitwala_ed.school_settings.doctype.meeting.meeting.meeting_has_permission",
    "School Event": "ifitwala_ed.school_settings.doctype.school_event.school_event.event_has_permission",
    "Student Group": "ifitwala_ed.schedule.doctype.student_group.student_group.group_has_permission",
	"Team": "ifitwala_ed.school_settings.doctype.team.team.team_has_permission"
}

has_upload_permission = {
	"Employee": "ifitwala_ed.hr.doctype.employee.employee.has_upload_permission"
}

default_roles = [
	{'role': 'Student', 'doctype':'Student', 'email_field': 'student_email'},
]

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

doc_events = {

	"User": {
		"after_insert": "frappe.contacts.doctype.contact.contact.update_contact",
		"validate": "ifitwala_ed.hr.doctype.employee.employee.validate_employee_role",
		"on_update": ["ifitwala_ed.hr.doctype.employee.employee.update_user_permissions"]
	},

    "ToDo": {
        "on_update": "ifitwala_ed.school_settings.doctype.meeting.meeting.update_minute_status",
        "on_trash": "ifitwala_ed.school_settings.doctype.meeting.meeting.update_minute_status"
    },

    "Contact": {
        "on_update": "ifitwala_ed.ifitwala_ed.utils.update_profile_from_contact"
    }
}


after_migrate = ["ifitwala_ed.setup.install.update_select_perm_after_install"]

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"ifitwala_ed.tasks.all"
# 	],
# 	"daily": [
# 		"ifitwala_ed.tasks.daily"
# 	],
	"hourly": [
 		"ifitwala_ed.school_settings.doctype.meeting.meeting.update_meeting_status"
 	]
# 	"weekly": [
# 		"ifitwala_ed.tasks.weekly"
# 	]
# 	"monthly": [
# 		"ifitwala_ed.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "ifitwala_ed.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ifitwala_ed.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ifitwala_ed.task.get_dashboard_data"
# }
