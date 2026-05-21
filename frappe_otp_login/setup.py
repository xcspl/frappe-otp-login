import frappe


def after_install():
	"""Create OTP Login Settings singleton with preset channels.
	Idempotent: safe to call multiple times."""
	if frappe.db.exists("OTP Login Settings", "OTP Login Settings"):
		settings = frappe.get_single("OTP Login Settings")
	else:
		settings = frappe.new_doc("OTP Login Settings")

	settings = frappe.get_single("OTP Login Settings")
	settings.enabled = 1
	settings.email_enabled = 1
	settings.email_search_field = "email"
	settings.resend_cooldown = 30

	# Add preset channels only if none exist (idempotent)
	existing_names = {c.channel_name for c in settings.http_channels}

	if "ntfy.sh" not in existing_names:
		ntfy = settings.append("http_channels")
		ntfy.channel_name = "ntfy.sh"
		ntfy.enabled = 0
		ntfy.method = "POST"
		ntfy.url = "https://ntfy.sh/{{ identifier }}"
		ntfy.auth_type = "None"
		ntfy.identifier_label = "Subscribed Topic"
		ntfy.user_field = "email"
		ntfy.identifier_placement = "URL Path"
		ntfy.content_type = "Raw (text/plain)"
		ntfy.message_template = "Your OTP code is {{ otp }}"

	if "Generic Indian SMS Provider" not in existing_names:
		sms = settings.append("http_channels")
		sms.channel_name = "Generic Indian SMS Provider"
		sms.enabled = 0
		sms.method = "GET"
		sms.url = "https://api.example.com/sendotp"
		sms.auth_type = "None"
		sms.content_type = "application/x-www-form-urlencoded"
		sms.identifier_label = "Phone Number"
		sms.user_field = "phone"
		sms.identifier_placement = "Query Parameter"
		sms.recipient_param = "mobiles"
		sms.otp_param = "message"
		sms.message_template = "{{ otp }} is your OTP for {{ site_name }}"

	settings.save(ignore_permissions=True)

	# Fix Desktop Icon type (Frappe sometimes sets it to NULL)
	for icon in frappe.get_all("Desktop Icon", filters={"app": "frappe_otp_login"}):
		frappe.db.set_value("Desktop Icon", icon.name, "type", "App")

	frappe.db.commit()


def before_uninstall():
	"""Cleanup before bench uninstall-app removes the app."""
	clear_otp_redis_keys()
	delete_desktop_icon()
	delete_channel_user_fields()


def clear_otp_redis_keys():
	"""Remove OTP codes, rate-limit counters, and failure counters from Redis."""
	try:
		prefix = frappe.cache.make_key("otp_login")
		cursor = 0
		deleted = 0
		while True:
			cursor, keys = frappe.cache.scan(cursor, match=f"{prefix}*", count=100)
			if keys:
				frappe.cache.delete(*keys)
				deleted += len(keys)
			if cursor == 0:
				break
		if deleted:
			print(f"Cleared {deleted} OTP Redis keys")
	except Exception:
		pass


def delete_channel_user_fields():
	"""Remove custom User fields created for HTTP channel identifiers."""
	try:
		settings = frappe.get_single("OTP Login Settings")
		for channel in settings.http_channels:
			fieldname = channel.user_field
			if fieldname and fieldname not in (
				"email", "username", "phone", "mobile_no",
				"first_name", "last_name", "full_name", "name",
			):
				frappe.db.delete("Custom Field", {"dt": "User", "fieldname": fieldname})
		frappe.db.commit()
	except Exception:
		pass


def delete_desktop_icon():
	try:
		frappe.db.delete("Desktop Icon", {"app": "frappe_otp_login"})
		frappe.db.commit()
	except Exception:
		pass
