#!/usr/bin/env python3
"""
generate_v2.py — Improved version of generate.py with:
  1. Information Gain injection (verifiable data point requirement)
  2. H2 heading randomization (variants for Pricing / Features / Limitations)
  3. Original angle (insight that wouldn't appear on vendor's own site)

Only the prompt section is modified; all other logic (API calls, cleanup, IndexNow) is unchanged.
"""

import os
import sys
import datetime
import re
import time
import requests
from openai import OpenAI

# make sibling helpers importable regardless of the current working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:  # semantic no-AI-slop rules, appended to the LLM system prompt
    from no_ai_slop_rules import SLOP_INSTRUCTIONS
except Exception:  # keep the generator resilient if the helper is unavailable
    SLOP_INSTRUCTIONS = ""

# --- model / client (same convention as deslop_rewrite.py) ------------------
api_key = os.environ.get('AGNES_API_KEY') or os.environ.get('MISTRAL_API_KEY')
if not api_key:
    print("Neither AGNES_API_KEY nor MISTRAL_API_KEY set. Abort.")
    raise SystemExit(1)
_base_url = ("https://apihub.agnes-ai.com/v1" if os.environ.get('AGNES_API_KEY')
             else "https://api.mistral.ai/v1")
client = OpenAI(api_key=api_key, base_url=_base_url)
MODEL_NAME = os.environ.get('AGNES_MODEL', 'agnes-3.0-flash')

# ========== B2B SaaS 长尾关键词库（1000 个，2026 联网调研补全）==========
keywords = [
    "best crm software 2026",
    "best crm for startups",
    "best crm for enterprises",
    "best free crm 2026",
    "best crm comparison 2026",
    "best crm for small business",
    "best crm for manufacturing",
    "best crm for construction",
    "best crm for real estate",
    "best crm for healthcare",
    "best erp software 2026",
    "best erp for small business 2026",
    "best erp for startups",
    "best erp for enterprises",
    "best free erp 2026",
    "best erp comparison 2026",
    "best erp for small business",
    "best erp for SaaS companies",
    "best erp for ecommerce",
    "best erp for manufacturing",
    "best erp for construction",
    "best erp for real estate",
    "best erp for healthcare",
    "best erp for financial services",
    "best pm software 2026",
    "best pm for small business 2026",
    "best pm for startups",
    "best pm for enterprises",
    "best free pm 2026",
    "best pm comparison 2026",
    "best pm for small business",
    "best pm for SaaS companies",
    "best pm for ecommerce",
    "best pm for manufacturing",
    "best pm for construction",
    "best pm for real estate",
    "best pm for healthcare",
    "best pm for financial services",
    "best accounting software 2026",
    "best accounting for small business 2026",
    "best accounting for startups",
    "best accounting for enterprises",
    "best free accounting 2026",
    "best accounting comparison 2026",
    "best accounting for small business",
    "best accounting for SaaS companies",
    "best accounting for ecommerce",
    "best accounting for manufacturing",
    "best accounting for construction",
    "best accounting for real estate",
    "best accounting for healthcare",
    "best accounting for financial services",
    "best hr software 2026",
    "best hr for small business 2026",
    "best hr for startups",
    "best hr for enterprises",
    "best free hr 2026",
    "best hr comparison 2026",
    "best hr for small business",
    "best hr for SaaS companies",
    "best hr for ecommerce",
    "best hr for manufacturing",
    "best hr for construction",
    "best hr for real estate",
    "best hr for healthcare",
    "best hr for financial services",
    "best helpdesk software 2026",
    "best helpdesk for small business 2026",
    "best helpdesk for startups",
    "best helpdesk for enterprises",
    "best free helpdesk 2026",
    "best helpdesk comparison 2026",
    "best helpdesk for small business",
    "best helpdesk for SaaS companies",
    "best helpdesk for ecommerce",
    "best helpdesk for manufacturing",
    "best helpdesk for construction",
    "best helpdesk for real estate",
    "best helpdesk for healthcare",
    "best helpdesk for financial services",
    "best bi software 2026",
    "best bi for small business 2026",
    "best bi for startups",
    "best bi for enterprises",
    "best free bi 2026",
    "best bi comparison 2026",
    "best bi for small business",
    "best bi for SaaS companies",
    "best bi for ecommerce",
    "best bi for manufacturing",
    "best bi for construction",
    "best bi for real estate",
    "best bi for healthcare",
    "best bi for financial services",
    "best marketing software 2026",
    "best marketing for small business 2026",
    "best marketing for startups",
    "best marketing for enterprises",
    "best free marketing 2026",
    "best marketing comparison 2026",
    "best marketing for small business",
    "best marketing for SaaS companies",
    "best marketing for ecommerce",
    "best marketing for manufacturing",
    "best marketing for construction",
    "best marketing for real estate",
    "best marketing for healthcare",
    "best marketing for financial services",
    "best esign software 2026",
    "best esign for small business 2026",
    "best esign for startups",
    "best esign for enterprises",
    "best free esign 2026",
    "best esign comparison 2026",
    "best esign for small business",
    "best esign for SaaS companies",
    "best esign for ecommerce",
    "best esign for manufacturing",
    "best esign for construction",
    "best esign for real estate",
    "best esign for healthcare",
    "best esign for financial services",
    "best inventory software 2026",
    "best inventory for small business 2026",
    "best inventory for startups",
    "best inventory for enterprises",
    "best free inventory 2026",
    "best inventory comparison 2026",
    "best inventory for small business",
    "best inventory for SaaS companies",
    "best inventory for ecommerce",
    "best inventory for manufacturing",
    "best inventory for construction",
    "best inventory for real estate",
    "best inventory for healthcare",
    "best inventory for financial services",
    "best security software 2026",
    "best security for small business 2026",
    "best security for startups",
    "best security for enterprises",
    "best free security 2026",
    "best security comparison 2026",
    "best security for small business",
    "best security for SaaS companies",
    "best security for ecommerce",
    "best security for manufacturing",
    "best security for construction",
    "best security for real estate",
    "best security for healthcare",
    "best security for financial services",
    "best workflow software 2026",
    "best workflow for small business 2026",
    "best workflow for startups",
    "best workflow for enterprises",
    "best free workflow 2026",
    "best workflow comparison 2026",
    "best workflow for small business",
    "best workflow for SaaS companies",
    "best workflow for ecommerce",
    "best workflow for manufacturing",
    "best workflow for construction",
    "best workflow for real estate",
    "best workflow for healthcare",
    "best workflow for financial services",
    "best ecommerce software 2026",
    "best ecommerce for small business 2026",
    "best ecommerce for startups",
    "best ecommerce for enterprises",
    "best free ecommerce 2026",
    "best ecommerce comparison 2026",
    "best ecommerce for small business",
    "best ecommerce for SaaS companies",
    "best ecommerce for ecommerce",
    "best ecommerce for manufacturing",
    "best ecommerce for construction",
    "best ecommerce for real estate",
    "best ecommerce for healthcare",
    "best ecommerce for financial services",
    "best chat software 2026",
    "best chat for small business 2026",
    "best chat for startups",
    "best chat for enterprises",
    "best free chat 2026",
    "best chat comparison 2026",
    "best chat for small business",
    "best chat for SaaS companies",
    "best chat for ecommerce",
    "best chat for manufacturing",
    "best chat for construction",
    "best chat for real estate",
    "best chat for healthcare",
    "best chat for financial services",
    "Salesforce review and pricing 2026",
    "is Salesforce worth it 2026",
    "Salesforce alternatives",
    "Salesforce vs competitors 2026",
    "Salesforce vs HubSpot",
    "Salesforce vs Zoho CRM",
    "Salesforce vs Pipedrive",
    "HubSpot review and pricing 2026",
    "is HubSpot worth it 2026",
    "HubSpot alternatives",
    "HubSpot vs competitors 2026",
    "HubSpot vs Salesforce",
    "HubSpot vs Zoho CRM",
    "HubSpot vs Pipedrive",
    "Zoho CRM review and pricing 2026",
    "is Zoho CRM worth it 2026",
    "Zoho CRM alternatives",
    "Zoho CRM vs competitors 2026",
    "Zoho CRM vs Salesforce",
    "Zoho CRM vs HubSpot",
    "Zoho CRM vs Pipedrive",
    "Pipedrive review and pricing 2026",
    "is Pipedrive worth it 2026",
    "Pipedrive alternatives",
    "Pipedrive vs competitors 2026",
    "Pipedrive vs Salesforce",
    "Pipedrive vs HubSpot",
    "Pipedrive vs Zoho CRM",
    "Salesflare review and pricing 2026",
    "is Salesflare worth it 2026",
    "Salesflare alternatives",
    "Salesflare vs competitors 2026",
    "Salesflare vs Salesforce",
    "Salesflare vs HubSpot",
    "Salesflare vs Zoho CRM",
    "Freshsales review and pricing 2026",
    "is Freshsales worth it 2026",
    "Freshsales alternatives",
    "Freshsales vs competitors 2026",
    "Freshsales vs Salesforce",
    "Freshsales vs HubSpot",
    "Copper review and pricing 2026",
    "is Copper worth it 2026",
    "Copper alternatives",
    "Copper vs competitors 2026",
    "Copper vs Salesforce",
    "Copper vs HubSpot",
    "Copper vs Zoho CRM",
    "Keap review and pricing 2026",
    "is Keap worth it 2026",
    "Keap alternatives",
    "Keap vs competitors 2026",
    "Keap vs Salesforce",
    "Keap vs HubSpot",
    "Keap vs Zoho CRM",
    "ActiveCampaign review and pricing 2026",
    "is ActiveCampaign worth it 2026",
    "ActiveCampaign alternatives",
    "ActiveCampaign vs competitors 2026",
    "ActiveCampaign vs Salesforce",
    "ActiveCampaign vs HubSpot",
    "ActiveCampaign vs Zoho CRM",
    "Less Annoying CRM review and pricing 2026",
    "is Less Annoying CRM worth it 2026",
    "Less Annoying CRM alternatives",
    "Less Annoying CRM vs competitors 2026",
    "Less Annoying CRM vs Salesforce",
    "Less Annoying CRM vs HubSpot",
    "Less Annoying CRM vs Zoho CRM",
    "Agile CRM review and pricing 2026",
    "is Agile CRM worth it 2026",
    "Agile CRM alternatives",
    "Agile CRM vs competitors 2026",
    "Agile CRM vs Salesforce",
    "Agile CRM vs HubSpot",
    "Agile CRM vs Zoho CRM",
    "Bitrix24 review and pricing 2026",
    "is Bitrix24 worth it 2026",
    "Bitrix24 alternatives",
    "Bitrix24 vs competitors 2026",
    "Bitrix24 vs Salesforce",
    "Bitrix24 vs HubSpot",
    "Bitrix24 vs Zoho CRM",
    "Microsoft Dynamics 365 review and pricing 2026",
    "is Microsoft Dynamics 365 worth it 2026",
    "Microsoft Dynamics 365 alternatives",
    "Microsoft Dynamics 365 vs competitors 2026",
    "Microsoft Dynamics 365 vs Salesforce",
    "Microsoft Dynamics 365 vs HubSpot",
    "Microsoft Dynamics 365 vs Zoho CRM",
    "Insightly review and pricing 2026",
    "is Insightly worth it 2026",
    "Insightly alternatives",
    "Insightly vs competitors 2026",
    "Insightly vs Salesforce",
    "Insightly vs HubSpot",
    "Insightly vs Zoho CRM",
    "Monday CRM review and pricing 2026",
    "is Monday CRM worth it 2026",
    "Monday CRM alternatives",
    "Monday CRM vs competitors 2026",
    "Monday CRM vs Salesforce",
    "Monday CRM vs HubSpot",
    "Monday CRM vs Zoho CRM",
    "Capsule review and pricing 2026",
    "is Capsule worth it 2026",
    "Capsule alternatives",
    "Capsule vs competitors 2026",
    "Capsule vs Salesforce",
    "Capsule vs HubSpot",
    "Capsule vs Zoho CRM",
    "Nutshell review and pricing 2026",
    "is Nutshell worth it 2026",
    "Nutshell alternatives",
    "Nutshell vs competitors 2026",
    "Nutshell vs Salesforce",
    "Nutshell vs HubSpot",
    "Nutshell vs Zoho CRM",
    "Close review and pricing 2026",
    "is Close worth it 2026",
    "Close alternatives",
    "Close vs competitors 2026",
    "Close vs Salesforce",
    "Close vs HubSpot",
    "Close vs Zoho CRM",
    "Streak review and pricing 2026",
    "is Streak worth it 2026",
    "Streak alternatives",
    "Streak vs competitors 2026",
    "Streak vs Salesforce",
    "Streak vs HubSpot",
    "Streak vs Zoho CRM",
    "Nimble review and pricing 2026",
    "is Nimble worth it 2026",
    "Nimble alternatives",
    "Nimble vs competitors 2026",
    "Nimble vs Salesforce",
    "Nimble vs HubSpot",
    "Nimble vs Zoho CRM",
    "NetSuite review and pricing 2026",
    "is NetSuite worth it 2026",
    "NetSuite alternatives",
    "NetSuite vs competitors 2026",
    "NetSuite vs SAP S/4HANA",
    "NetSuite vs SAP Business One",
    "NetSuite vs Oracle ERP Cloud",
    "SAP S/4HANA review and pricing 2026",
    "is SAP S/4HANA worth it 2026",
    "SAP S/4HANA alternatives",
    "SAP S/4HANA vs competitors 2026",
    "SAP S/4HANA vs NetSuite",
    "SAP S/4HANA vs SAP Business One",
    "SAP S/4HANA vs Oracle ERP Cloud",
    "SAP Business One review and pricing 2026",
    "is SAP Business One worth it 2026",
    "SAP Business One alternatives",
    "SAP Business One vs competitors 2026",
    "SAP Business One vs NetSuite",
    "SAP Business One vs SAP S/4HANA",
    "SAP Business One vs Oracle ERP Cloud",
    "Oracle ERP Cloud review and pricing 2026",
    "is Oracle ERP Cloud worth it 2026",
    "Oracle ERP Cloud alternatives",
    "Oracle ERP Cloud vs competitors 2026",
    "Oracle ERP Cloud vs NetSuite",
    "Oracle ERP Cloud vs SAP S/4HANA",
    "Oracle ERP Cloud vs SAP Business One",
    "Dynamics 365 Business Central review and pricing 2026",
    "is Dynamics 365 Business Central worth it 2026",
    "Dynamics 365 Business Central alternatives",
    "Dynamics 365 Business Central vs competitors 2026",
    "Dynamics 365 Business Central vs NetSuite",
    "Dynamics 365 Business Central vs SAP S/4HANA",
    "Dynamics 365 Business Central vs SAP Business One",
    "Acumatica review and pricing 2026",
    "is Acumatica worth it 2026",
    "Acumatica alternatives",
    "Acumatica vs competitors 2026",
    "Acumatica vs NetSuite",
    "Acumatica vs SAP S/4HANA",
    "Acumatica vs SAP Business One",
    "Epicor Kinetic review and pricing 2026",
    "is Epicor Kinetic worth it 2026",
    "Epicor Kinetic alternatives",
    "Epicor Kinetic vs competitors 2026",
    "Epicor Kinetic vs NetSuite",
    "Epicor Kinetic vs SAP S/4HANA",
    "Epicor Kinetic vs SAP Business One",
    "Odoo review and pricing 2026",
    "is Odoo worth it 2026",
    "Odoo alternatives",
    "Odoo vs competitors 2026",
    "Odoo vs NetSuite",
    "Odoo vs SAP S/4HANA",
    "Odoo vs SAP Business One",
    "Infor M3 review and pricing 2026",
    "is Infor M3 worth it 2026",
    "Infor M3 alternatives",
    "Infor M3 vs competitors 2026",
    "Infor M3 vs NetSuite",
    "Infor M3 vs SAP S/4HANA",
    "Infor M3 vs SAP Business One",
    "IFS review and pricing 2026",
    "is IFS worth it 2026",
    "IFS alternatives",
    "IFS vs competitors 2026",
    "IFS vs NetSuite",
    "IFS vs SAP S/4HANA",
    "IFS vs SAP Business One",
    "Sage Intacct review and pricing 2026",
    "is Sage Intacct worth it 2026",
    "Sage Intacct alternatives",
    "Sage Intacct vs competitors 2026",
    "Sage Intacct vs NetSuite",
    "Sage Intacct vs SAP S/4HANA",
    "Sage Intacct vs SAP Business One",
    "Sage X3 review and pricing 2026",
    "is Sage X3 worth it 2026",
    "Sage X3 alternatives",
    "Sage X3 vs competitors 2026",
    "Sage X3 vs NetSuite",
    "Sage X3 vs SAP S/4HANA",
    "Sage X3 vs SAP Business One",
    "QAD Adaptive review and pricing 2026",
    "is QAD Adaptive worth it 2026",
    "QAD Adaptive alternatives",
    "QAD Adaptive vs competitors 2026",
    "QAD Adaptive vs NetSuite",
    "QAD Adaptive vs SAP S/4HANA",
    "QAD Adaptive vs SAP Business One",
    "MRPeasy review and pricing 2026",
    "is MRPeasy worth it 2026",
    "MRPeasy alternatives",
    "MRPeasy vs competitors 2026",
    "MRPeasy vs NetSuite",
    "MRPeasy vs SAP S/4HANA",
    "MRPeasy vs SAP Business One",
    "Katana review and pricing 2026",
    "is Katana worth it 2026",
    "Katana alternatives",
    "Katana vs competitors 2026",
    "Katana vs NetSuite",
    "Katana vs SAP S/4HANA",
    "Katana vs SAP Business One",
    "Plex review and pricing 2026",
    "is Plex worth it 2026",
    "Plex alternatives",
    "Plex vs competitors 2026",
    "Plex vs NetSuite",
    "Plex vs SAP S/4HANA",
    "Plex vs SAP Business One",
    "JobBOSS review and pricing 2026",
    "is JobBOSS worth it 2026",
    "JobBOSS alternatives",
    "JobBOSS vs competitors 2026",
    "JobBOSS vs NetSuite",
    "JobBOSS vs SAP S/4HANA",
    "JobBOSS vs SAP Business One",
    "SYSPRO review and pricing 2026",
    "is SYSPRO worth it 2026",
    "SYSPRO alternatives",
    "SYSPRO vs competitors 2026",
    "SYSPRO vs NetSuite",
    "SYSPRO vs SAP S/4HANA",
    "SYSPRO vs SAP Business One",
    "Rootstock review and pricing 2026",
    "is Rootstock worth it 2026",
    "Rootstock alternatives",
    "Rootstock vs competitors 2026",
    "Rootstock vs NetSuite",
    "Rootstock vs SAP S/4HANA",
    "Rootstock vs SAP Business One",
    "Oracle Fusion Cloud review and pricing 2026",
    "is Oracle Fusion Cloud worth it 2026",
    "Oracle Fusion Cloud alternatives",
    "Oracle Fusion Cloud vs competitors 2026",
    "Oracle Fusion Cloud vs NetSuite",
    "Oracle Fusion Cloud vs SAP S/4HANA",
    "Oracle Fusion Cloud vs SAP Business One",
    "ClickUp review and pricing 2026",
    "is ClickUp worth it 2026",
    "ClickUp alternatives",
    "ClickUp vs competitors 2026",
    "ClickUp vs Asana",
    "ClickUp vs Monday.com",
    "ClickUp vs Jira",
    "Asana review and pricing 2026",
    "is Asana worth it 2026",
    "Asana alternatives",
    "Asana vs competitors 2026",
    "Asana vs ClickUp",
    "Asana vs Monday.com",
    "Asana vs Jira",
    "Monday.com review and pricing 2026",
    "is Monday.com worth it 2026",
    "Monday.com alternatives",
    "Monday.com vs competitors 2026",
    "Monday.com vs ClickUp",
    "Monday.com vs Asana",
    "Monday.com vs Jira",
    "Jira review and pricing 2026",
    "is Jira worth it 2026",
    "Jira alternatives",
    "Jira vs competitors 2026",
    "Jira vs ClickUp",
    "Jira vs Asana",
    "Jira vs Monday.com",
    "Notion review and pricing 2026",
    "is Notion worth it 2026",
    "Notion alternatives",
    "Notion vs competitors 2026",
    "Notion vs ClickUp",
    "Notion vs Asana",
    "Notion vs Monday.com",
    "Trello review and pricing 2026",
    "is Trello worth it 2026",
    "Trello alternatives",
    "Trello vs competitors 2026",
    "Trello vs ClickUp",
    "Trello vs Asana",
    "Trello vs Monday.com",
    "Wrike review and pricing 2026",
    "is Wrike worth it 2026",
    "Wrike alternatives",
    "Wrike vs competitors 2026",
    "Wrike vs ClickUp",
    "Wrike vs Asana",
    "Wrike vs Monday.com",
    "Smartsheet review and pricing 2026",
    "is Smartsheet worth it 2026",
    "Smartsheet alternatives",
    "Smartsheet vs competitors 2026",
    "Smartsheet vs ClickUp",
    "Smartsheet vs Asana",
    "Smartsheet vs Monday.com",
    "Teamwork review and pricing 2026",
    "is Teamwork worth it 2026",
    "Teamwork alternatives",
    "Teamwork vs competitors 2026",
    "Teamwork vs ClickUp",
    "Teamwork vs Asana",
    "Teamwork vs Monday.com",
    "Basecamp review and pricing 2026",
    "is Basecamp worth it 2026",
    "Basecamp alternatives",
    "Basecamp vs competitors 2026",
    "Basecamp vs ClickUp",
    "Basecamp vs Asana",
    "Basecamp vs Monday.com",
    "Linear review and pricing 2026",
    "is Linear worth it 2026",
    "Linear alternatives",
    "Linear vs competitors 2026",
    "Linear vs ClickUp",
    "Linear vs Asana",
    "Linear vs Monday.com",
    "Motion review and pricing 2026",
    "is Motion worth it 2026",
    "Motion alternatives",
    "Motion vs competitors 2026",
    "Motion vs ClickUp",
    "Motion vs Asana",
    "Motion vs Monday.com",
    "Akiflow review and pricing 2026",
    "is Akiflow worth it 2026",
    "Akiflow alternatives",
    "Akiflow vs competitors 2026",
    "Akiflow vs ClickUp",
    "Akiflow vs Asana",
    "Akiflow vs Monday.com",
    "Todoist review and pricing 2026",
    "is Todoist worth it 2026",
    "Todoist alternatives",
    "Todoist vs competitors 2026",
    "Todoist vs ClickUp",
    "Todoist vs Asana",
    "Todoist vs Monday.com",
    "Height review and pricing 2026",
    "is Height worth it 2026",
    "Height alternatives",
    "Height vs competitors 2026",
    "Height vs ClickUp",
    "Height vs Asana",
    "Height vs Monday.com",
    "Airtable review and pricing 2026",
    "is Airtable worth it 2026",
    "Airtable alternatives",
    "Airtable vs competitors 2026",
    "Airtable vs ClickUp",
    "Airtable vs Asana",
    "Airtable vs Monday.com",
    "Microsoft Project review and pricing 2026",
    "is Microsoft Project worth it 2026",
    "Microsoft Project alternatives",
    "Microsoft Project vs competitors 2026",
    "Microsoft Project vs ClickUp",
    "Microsoft Project vs Asana",
    "Microsoft Project vs Monday.com",
    "Zoho Projects review and pricing 2026",
    "is Zoho Projects worth it 2026",
    "Zoho Projects alternatives",
    "Zoho Projects vs competitors 2026",
    "Zoho Projects vs ClickUp",
    "Zoho Projects vs Asana",
    "Zoho Projects vs Monday.com",
    "Adobe Workfront review and pricing 2026",
    "is Adobe Workfront worth it 2026",
    "Adobe Workfront alternatives",
    "Adobe Workfront vs competitors 2026",
    "Adobe Workfront vs ClickUp",
    "Adobe Workfront vs Asana",
    "Adobe Workfront vs Monday.com",
    "Smartsuite review and pricing 2026",
    "is Smartsuite worth it 2026",
    "Smartsuite alternatives",
    "Smartsuite vs competitors 2026",
    "Smartsuite vs ClickUp",
    "Smartsuite vs Asana",
    "Smartsuite vs Monday.com",
    "QuickBooks review and pricing 2026",
    "is QuickBooks worth it 2026",
    "QuickBooks alternatives",
    "QuickBooks vs competitors 2026",
    "QuickBooks vs Xero",
    "QuickBooks vs FreshBooks",
    "QuickBooks vs Wave",
    "Xero review and pricing 2026",
    "is Xero worth it 2026",
    "Xero alternatives",
    "Xero vs competitors 2026",
    "Xero vs QuickBooks",
    "Xero vs FreshBooks",
    "Xero vs Wave",
    "FreshBooks review and pricing 2026",
    "is FreshBooks worth it 2026",
    "FreshBooks alternatives",
    "FreshBooks vs competitors 2026",
    "FreshBooks vs QuickBooks",
    "FreshBooks vs Xero",
    "FreshBooks vs Wave",
    "Wave review and pricing 2026",
    "is Wave worth it 2026",
    "Wave alternatives",
    "Wave vs competitors 2026",
    "Wave vs QuickBooks",
    "Wave vs Xero",
    "Wave vs FreshBooks",
    "Sage review and pricing 2026",
    "is Sage worth it 2026",
    "Sage alternatives",
    "Sage vs competitors 2026",
    "Sage vs QuickBooks",
    "Sage vs Xero",
    "Sage vs FreshBooks",
    "Zoho Books review and pricing 2026",
    "is Zoho Books worth it 2026",
    "Zoho Books alternatives",
    "Zoho Books vs competitors 2026",
    "Zoho Books vs QuickBooks",
    "Zoho Books vs Xero",
    "Zoho Books vs FreshBooks",
    "FreeAgent review and pricing 2026",
    "is FreeAgent worth it 2026",
    "FreeAgent alternatives",
    "FreeAgent vs competitors 2026",
    "FreeAgent vs QuickBooks",
    "FreeAgent vs Xero",
    "FreeAgent vs FreshBooks",
    "Bill.com review and pricing 2026",
    "is Bill.com worth it 2026",
    "Bill.com alternatives",
    "Bill.com vs competitors 2026",
    "Bill.com vs QuickBooks",
    "Bill.com vs Xero",
    "Bill.com vs FreshBooks",
    "Expensify review and pricing 2026",
    "is Expensify worth it 2026",
    "Expensify alternatives",
    "Expensify vs competitors 2026",
    "Expensify vs QuickBooks",
    "Expensify vs Xero",
    "Expensify vs FreshBooks",
    "Ramp review and pricing 2026",
    "is Ramp worth it 2026",
    "Ramp alternatives",
    "Ramp vs competitors 2026",
    "Ramp vs QuickBooks",
    "Ramp vs Xero",
    "Ramp vs FreshBooks",
    "Brex review and pricing 2026",
    "is Brex worth it 2026",
    "Brex alternatives",
    "Brex vs competitors 2026",
    "Brex vs QuickBooks",
    "Brex vs Xero",
    "Brex vs FreshBooks",
    "Bench review and pricing 2026",
    "is Bench worth it 2026",
    "Bench alternatives",
    "Bench vs competitors 2026",
    "Bench vs QuickBooks",
    "Bench vs Xero",
    "Bench vs FreshBooks",
    "NetSuite vs QuickBooks",
    "NetSuite vs Xero",
    "NetSuite vs FreshBooks",
    "Kashoo review and pricing 2026",
    "is Kashoo worth it 2026",
    "Kashoo alternatives",
    "Kashoo vs competitors 2026",
    "Kashoo vs QuickBooks",
    "Kashoo vs Xero",
    "Kashoo vs FreshBooks",
    "AccountEdge review and pricing 2026",
    "is AccountEdge worth it 2026",
    "AccountEdge alternatives",
    "AccountEdge vs competitors 2026",
    "AccountEdge vs QuickBooks",
    "AccountEdge vs Xero",
    "AccountEdge vs FreshBooks",
    "BambooHR review and pricing 2026",
    "is BambooHR worth it 2026",
    "BambooHR alternatives",
    "BambooHR vs competitors 2026",
    "BambooHR vs Gusto",
    "BambooHR vs Rippling",
    "BambooHR vs ADP",
    "Gusto review and pricing 2026",
    "is Gusto worth it 2026",
    "Gusto alternatives",
    "Gusto vs competitors 2026",
    "Gusto vs BambooHR",
    "Gusto vs Rippling",
    "Gusto vs ADP",
    "Rippling review and pricing 2026",
    "is Rippling worth it 2026",
    "Rippling alternatives",
    "Rippling vs competitors 2026",
    "Rippling vs BambooHR",
    "Rippling vs Gusto",
    "Rippling vs ADP",
    "ADP review and pricing 2026",
    "is ADP worth it 2026",
    "ADP alternatives",
    "ADP vs competitors 2026",
    "ADP vs BambooHR",
    "ADP vs Gusto",
    "ADP vs Rippling",
    "Paychex review and pricing 2026",
    "is Paychex worth it 2026",
    "Paychex alternatives",
    "Paychex vs competitors 2026",
    "Paychex vs BambooHR",
    "Paychex vs Gusto",
    "Paychex vs Rippling",
    "Workday review and pricing 2026",
    "is Workday worth it 2026",
    "Workday alternatives",
    "Workday vs competitors 2026",
    "Workday vs BambooHR",
    "Workday vs Gusto",
    "Workday vs Rippling",
    "UKG review and pricing 2026",
    "is UKG worth it 2026",
    "UKG alternatives",
    "UKG vs competitors 2026",
    "UKG vs BambooHR",
    "UKG vs Gusto",
    "UKG vs Rippling",
    "Paylocity review and pricing 2026",
    "is Paylocity worth it 2026",
    "Paylocity alternatives",
    "Paylocity vs competitors 2026",
    "Paylocity vs BambooHR",
    "Paylocity vs Gusto",
    "Paylocity vs Rippling",
    "Zenefits review and pricing 2026",
    "is Zenefits worth it 2026",
    "Zenefits alternatives",
    "Zenefits vs competitors 2026",
    "Zenefits vs BambooHR",
    "Zenefits vs Gusto",
    "Zenefits vs Rippling",
    "Namely review and pricing 2026",
    "is Namely worth it 2026",
    "Namely alternatives",
    "Namely vs competitors 2026",
    "Namely vs BambooHR",
    "Namely vs Gusto",
    "Namely vs Rippling",
    "Lattice review and pricing 2026",
    "is Lattice worth it 2026",
    "Lattice alternatives",
    "Lattice vs competitors 2026",
    "Lattice vs BambooHR",
    "Lattice vs Gusto",
    "Lattice vs Rippling",
    "Culture Amp review and pricing 2026",
    "is Culture Amp worth it 2026",
    "Culture Amp alternatives",
    "Culture Amp vs competitors 2026",
    "Culture Amp vs BambooHR",
    "Culture Amp vs Gusto",
    "Culture Amp vs Rippling",
    "Lever review and pricing 2026",
    "is Lever worth it 2026",
    "Lever alternatives",
    "Lever vs competitors 2026",
    "Lever vs BambooHR",
    "Lever vs Gusto",
    "Lever vs Rippling",
    "Greenhouse review and pricing 2026",
    "is Greenhouse worth it 2026",
    "Greenhouse alternatives",
    "Greenhouse vs competitors 2026",
    "Greenhouse vs BambooHR",
    "Greenhouse vs Gusto",
    "Greenhouse vs Rippling",
    "iCIMS review and pricing 2026",
    "is iCIMS worth it 2026",
    "iCIMS alternatives",
    "iCIMS vs competitors 2026",
    "iCIMS vs BambooHR",
    "iCIMS vs Gusto",
    "iCIMS vs Rippling",
    "SmartRecruiters review and pricing 2026",
    "is SmartRecruiters worth it 2026",
    "SmartRecruiters alternatives",
    "SmartRecruiters vs competitors 2026",
    "SmartRecruiters vs BambooHR",
    "SmartRecruiters vs Gusto",
    "SmartRecruiters vs Rippling",
    "Deel review and pricing 2026",
    "is Deel worth it 2026",
    "Deel alternatives",
    "Deel vs competitors 2026",
    "Deel vs BambooHR",
    "Deel vs Gusto",
    "Deel vs Rippling",
    "Remote review and pricing 2026",
    "is Remote worth it 2026",
    "Remote alternatives",
    "Remote vs competitors 2026",
    "Remote vs BambooHR",
    "Remote vs Gusto",
    "Remote vs Rippling",
    "Papaya Global review and pricing 2026",
    "is Papaya Global worth it 2026",
    "Papaya Global alternatives",
    "Papaya Global vs competitors 2026",
    "Papaya Global vs BambooHR",
    "Papaya Global vs Gusto",
    "Papaya Global vs Rippling",
    "Oyster review and pricing 2026",
    "is Oyster worth it 2026",
    "Oyster alternatives",
    "Oyster vs competitors 2026",
    "Oyster vs BambooHR",
    "Oyster vs Gusto",
    "Oyster vs Rippling",
    "Zendesk review and pricing 2026",
    "is Zendesk worth it 2026",
    "Zendesk alternatives",
    "Zendesk vs competitors 2026",
    "Zendesk vs Freshdesk",
    "Zendesk vs Intercom",
    "Zendesk vs Help Scout",
    "Freshdesk review and pricing 2026",
    "is Freshdesk worth it 2026",
    "Freshdesk alternatives",
    "Freshdesk vs competitors 2026",
    "Freshdesk vs Zendesk",
    "Freshdesk vs Intercom",
    "Freshdesk vs Help Scout",
    "Intercom review and pricing 2026",
    "is Intercom worth it 2026",
    "Intercom alternatives",
    "Intercom vs competitors 2026",
    "Intercom vs Zendesk",
    "Intercom vs Freshdesk",
    "Intercom vs Help Scout",
    "Help Scout review and pricing 2026",
    "is Help Scout worth it 2026",
    "Help Scout alternatives",
    "Help Scout vs competitors 2026",
    "Help Scout vs Zendesk",
    "Help Scout vs Freshdesk",
    "Help Scout vs Intercom",
    "Front review and pricing 2026",
    "is Front worth it 2026",
    "Front alternatives",
    "Front vs competitors 2026",
    "Front vs Zendesk",
    "Front vs Freshdesk",
    "Front vs Intercom",
    "Gorgias review and pricing 2026",
    "is Gorgias worth it 2026",
    "Gorgias alternatives",
    "Gorgias vs competitors 2026",
    "Gorgias vs Zendesk",
    "Gorgias vs Freshdesk",
    "Gorgias vs Intercom",
    "Jira Service Management review and pricing 2026",
    "is Jira Service Management worth it 2026",
    "Jira Service Management alternatives",
    "Jira Service Management vs competitors 2026",
    "Jira Service Management vs Zendesk",
    "Jira Service Management vs Freshdesk",
    "Jira Service Management vs Intercom",
    "ServiceNow review and pricing 2026",
    "is ServiceNow worth it 2026",
    "ServiceNow alternatives",
    "ServiceNow vs competitors 2026",
    "ServiceNow vs Zendesk",
    "ServiceNow vs Freshdesk",
    "ServiceNow vs Intercom",
    "HaloITSM review and pricing 2026",
    "is HaloITSM worth it 2026",
    "HaloITSM alternatives",
    "HaloITSM vs competitors 2026",
    "HaloITSM vs Zendesk",
    "HaloITSM vs Freshdesk",
    "HaloITSM vs Intercom",
    "ManageEngine review and pricing 2026",
    "is ManageEngine worth it 2026",
    "ManageEngine alternatives",
    "ManageEngine vs competitors 2026",
    "ManageEngine vs Zendesk",
    "ManageEngine vs Freshdesk",
    "ManageEngine vs Intercom",
    "Zoho Desk review and pricing 2026",
    "is Zoho Desk worth it 2026",
    "Zoho Desk alternatives",
    "Zoho Desk vs competitors 2026",
    "Zoho Desk vs Zendesk",
    "Zoho Desk vs Freshdesk",
    "Zoho Desk vs Intercom",
    "LiveAgent review and pricing 2026",
    "is LiveAgent worth it 2026",
    "LiveAgent alternatives",
    "LiveAgent vs competitors 2026",
    "LiveAgent vs Zendesk",
    "LiveAgent vs Freshdesk",
    "LiveAgent vs Intercom",
    "Tableau review and pricing 2026",
    "is Tableau worth it 2026",
    "Tableau alternatives",
    "Tableau vs competitors 2026",
    "Tableau vs Power BI",
    "Tableau vs Looker",
    "Tableau vs Qlik",
    "Power BI review and pricing 2026",
    "is Power BI worth it 2026",
    "Power BI alternatives",
    "Power BI vs competitors 2026",
    "Power BI vs Tableau",
    "Power BI vs Looker",
    "Power BI vs Qlik",
    "Looker review and pricing 2026",
    "is Looker worth it 2026",
    "Looker alternatives",
    "Looker vs competitors 2026",
    "Looker vs Tableau",
    "Looker vs Power BI",
    "Looker vs Qlik",
    "Qlik review and pricing 2026",
    "is Qlik worth it 2026",
    "Qlik alternatives",
    "Qlik vs competitors 2026",
    "Qlik vs Tableau",
    "Qlik vs Power BI",
    "Qlik vs Looker",
    "Snowflake review and pricing 2026",
    "is Snowflake worth it 2026",
    "Snowflake alternatives",
    "Snowflake vs competitors 2026",
    "Snowflake vs Tableau",
    "Snowflake vs Power BI",
    "Snowflake vs Looker",
    "Domo review and pricing 2026",
    "is Domo worth it 2026",
    "Domo alternatives",
    "Domo vs competitors 2026",
    "Domo vs Tableau",
    "Domo vs Power BI",
    "Domo vs Looker",
    "Sisense review and pricing 2026",
    "is Sisense worth it 2026",
    "Sisense alternatives",
    "Sisense vs competitors 2026",
    "Sisense vs Tableau",
    "Sisense vs Power BI",
    "Sisense vs Looker",
    "Metabase review and pricing 2026",
    "is Metabase worth it 2026",
    "Metabase alternatives",
    "Metabase vs competitors 2026",
    "Metabase vs Tableau",
    "Metabase vs Power BI",
    "Metabase vs Looker",
    "Looker Studio review and pricing 2026",
    "is Looker Studio worth it 2026",
    "Looker Studio alternatives",
    "Looker Studio vs competitors 2026",
    "Looker Studio vs Tableau",
    "Looker Studio vs Power BI",
    "Looker Studio vs Looker",
    "ThoughtSpot review and pricing 2026"
]

# ========== 关键词轮换 ==========
INDEX_FILE = "keyword_index.txt"
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r") as f:
        try:
            index = int(f.read().strip())
        except:
            index = 0
else:
    index = 0

def _slug_of(kw):
    """与下方生成文件名用的规则保持一致。"""
    return re.sub(r'[^a-z0-9]+', '-', kw.strip().lower())[:50]


# 已发布文章的 slug 集合（文件名形如 2026-06-07-bamboohr-vs-gusto-pricing.md）
_posts_dir = os.path.join("content", "posts")
_published = set()
if os.path.isdir(_posts_dir):
    for _fn in os.listdir(_posts_dir):
        if _fn.endswith(".md"):
            _m = re.match(r"\d{4}-\d{2}-\d{2}-(.*)\.md$", _fn)
            _published.add(_m.group(1) if _m else _fn[:-3])

# 从轮转位置往后找第一个「还没发过」的关键词，避免产出近似重复内容
# （重复/近重复正是 AdSense low-value content 的负面信号）
chosen_i = index % len(keywords)
keyword = keywords[chosen_i]
for _offset in range(len(keywords)):
    _i = (index + _offset) % len(keywords)
    if _slug_of(keywords[_i]) not in _published:
        chosen_i = _i
        keyword = keywords[_i]
        break

next_index = (chosen_i + 1) % len(keywords)

# 按关键词内容判定分类（原先按索引，词库扩充后索引映射会全部错判成 Comparisons）
_kw_low = keyword.lower()
if "crm" in _kw_low or "salesforce" in _kw_low or "hubspot" in _kw_low or "pipedrive" in _kw_low:
    category = "CRM"
elif "erp" in _kw_low or "netsuite" in _kw_low or "sap" in _kw_low or "inventory" in _kw_low:
    category = "ERP"
elif any(t in _kw_low for t in ("project", "asana", "monday", "wrike", "clickup", "kanban", "trello")):
    category = "Project Management"
else:
    category = "Comparisons"

with open(INDEX_FILE, "w") as f:
    f.write(str(next_index))

today = datetime.date.today().strftime("%Y-%m-%d")

# ========== 专业软件评测 Prompt (v3 — full deai 33-pattern constraints + Information Gain + Original angle) ==========
# Based on blader/humanizer v2.8.0 (33 AI writing patterns) + Leonxlnx/taste-skill (anti-default strategies)
prompt = f"""
You are a B2B software consultant who has actually evaluated, implemented, and migrated business tools for real teams. Write a practical, honest review based on the keyword "{keyword}".

============================================================
PROHIBITED VOCABULARY — DO NOT USE ANY OF THESE WORDS
============================================================
NEVER use: crucial, pivotal, vital, delve, showcase, tapestry (abstract), landscape (abstract), vibrant, testament, underscore, fosters, intricate, interplay, nestled, breathtaking, groundbreaking, in the heart of, robust, seamless(ly), unparalleled, unlock, unleash, harness, game-changer, revolutionary, realm, daunting, embark on, cutting-edge, best-in-class, world-class, state-of-the-art

============================================================
PROHIBITED PHRASES & STRUCTURES
============================================================
- "Not only...but also..." — NEVER. Rewrite as direct statement.
- "It's not just about...it's..." — NEVER.
- "From X to Y" (fake range) — NEVER. Just list what you mean.
- "Let's dive in" / "Let's explore" / "Here's what you need to know" — NEVER.
- "In conclusion" / "To sum up" / "Bottom line" / "Wrapping up" — NEVER.
- "The future looks bright" / "Exciting times lie ahead" — NEVER.
- "Experts believe" / "Observers have noted" / "Industry reports suggest" — NEVER. Say WHO specifically.
- "serves as" / "stands as" / "marks a pivotal moment" — NEVER. Use "is" / "are" / "has".
- "I hope this helps" / "Let me know if" / "Would you like me to" — NEVER (chatbot residue).
- "Despite its challenges...continues to thrive" — NEVER (template filler).
- "X is the Y of Z" / "X becomes a trap" — NEVER (aphorism formula).
- "Honestly?" / "Look," / "Here's the thing" — NEVER (fake intimacy opener).
- Three-item parallelism (A, B, and C recurring densely) — AVOID. Use 2 or 4 items naturally.
- Synonym cycling (same entity called 3+ different names) — AVOID. Repeat the clearest term.

============================================================
PUNCTUATION RULES (HIGHEST PRIORITY)
============================================================
- NO em dashes (—) or en dashes (–) — ZERO. Use periods, commas, or colons instead.
- NO curly/smart quotes (""). Use straight quotes ("").
- NO emoji anywhere.
- Headings MUST use sentence case (only first word capitalized, plus proper nouns). Example: "What you'll actually pay" NOT "What You'll Actually Pay".

============================================================
STYLE REQUIREMENTS
============================================================
- Use "is/are/has" directly. Never "serves as" or "boasts" instead of simple be-verbs.
- Sentence length MUST vary. Avoid 3+ consecutive sentences of similar length (15-25 words is the AI comfort zone — break out of it deliberately).
- Paragraph size MUST vary. Some paragraphs = one sentence. Some = 5+ sentences. Never uniform 3-5 sentence blocks.
- Remove all "-ing" padding clauses: no ", highlighting...", ", underscoring...", ", emphasizing...", ", reflecting...", ", showcasing..."
- If you don't know something, say so directly. Never use "remains unclear" or "details are limited" as filler.
- No "rule of three" density. Break any pattern where three items are listed in parallel across consecutive sentences.
- Use the active voice. Name who does what. "You do not need a config file" not "No configuration file needed."
- Drop filler phrases: "In order to" → "To"; "Due to the fact that" → "Because"; "It is important to note that" → just say it.
- Use only ONE qualifier ("may" OR "might", not "could potentially possibly have some effect").
- No bold formatting within body text. Use italics sparingly (max 3 per article) for genuine emphasis.
- No "key: value" inline lists. Rewrite as natural paragraphs.

============================================================
CONTENT GUIDELINES
============================================================
1. YAML metadata block (no level-1 heading in body):
---
title: "Specific, benefit-driven title including the keyword naturally"
date: {today}
slug: "auto-generated-english-slug"
draft: false
tags: ["{category}"]
description: "SEO description under 160 chars summarizing the review"
---

2. Article opening:
   - Do NOT open with a broad industry statement ("The CRM market has grown..."). Start with a pricing gotcha, a specific workflow frustration, a strong opinion, or a concrete real-world scenario.
   - First paragraph should feel like someone who's been burned by bad software talking, not a Wikipedia entry.

3. Body structure (Markdown):
   - Use ## (H2) for main sections, ### (H3) for sub-sections. Never use ### as top-level.
   - H2 heading variants: Pick naturally from these sets based on article flow:
     * Pricing: "What you'll actually pay" / "Pricing tiers and hidden costs" / "Is it worth the money?" / "Breaking down the pricing"
     * Features: "What sets it apart" / "Features that actually matter" / "Where it shines (and where it doesn't)"
     * Limitations: "The rough edges" / "What users complain about" / "Where it falls short"
   - H2 immediately followed by real content, not a sentence that just restates the heading.
   - Include at least one comparison table with 4+ rows covering pricing, features, and team-size fit.
   - Highlight 2-3 specific features with daily-use context. Don't name-drop — explain what a team gains or loses.
   - Cover genuine strengths AND real limitations. Specific: "The mobile app lacks offline mode" beats "Mobile experience has room for improvement."
   - Include one insight unlikely to appear on the vendor's own site: hidden costs, integration friction, migration effort, or community complaints.

4. Article ending:
   - Do NOT write a "conclusion" section. No formal closing header.
   - End with a grounded recommendation for a specific reader profile (company size, budget, industry). Weave it into the closing paragraph naturally.
   - If there's a concrete next step or development to watch, mention it. Otherwise, a short, direct final sentence.

5. Information gain (CRITICAL):
   - Include at least 1 real, verifiable data point not easily found in top 5 Google results: specific pricing tier from vendor site, actual G2 rating with date, known integration limitation from official docs, or a recent product update timeline.
   - DO NOT fabricate data. If uncertain, frame as general observation rather than fake statistic.
   - Attribute all claims to specific sources: "G2 reviews as of June 2026 show..." not "Users report..."

6. Original angle (CRITICAL):
   - Provide at least one insight the vendor's marketing pages would NOT include: Reddit/forum sentiment, integration friction users report, a limitation the marketing glosses over, or a use case where another tool is clearly better.

7. Tone: Confident, direct, conversational. Like explaining to a colleague over coffee. Use contractions. Back claims with specifics, never adjectives. Occasional first-person ("I've seen teams struggle with...") is welcome. Allow some asymmetry — not every paragraph needs the same structure.

8. Output ONLY the Markdown article from "---" to the last line. No commentary, no wrapping code blocks (```), nothing outside the article.
"""

prompt = prompt + ("\n\n" + SLOP_INSTRUCTIONS if SLOP_INSTRUCTIONS else "")

# ========== API 调用(重试+超时)==========
MAX_RETRIES = 3
RETRY_DELAY = 10
TIMEOUT_SECONDS = 600

article_text = None
for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"🔁 Attempt {attempt} / {MAX_RETRIES} ...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.75,
            max_tokens=3000,
            timeout=TIMEOUT_SECONDS,
        )
        article_text = response.choices[0].message.content.strip()
        print(f"📝 Raw API response length: {len(article_text)}")
        print("✅ API call succeeded.")
        break
    except Exception as e:
        print(f"❌ Attempt {attempt} failed: {e}")
        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"⏳ Retrying in {wait} seconds...")
            time.sleep(wait)
        else:
            print("⛔ All retries exhausted. Exiting.")
            exit(1)

# ========== 清理异常输出 ==========
# Step 0: dump raw response for debugging
print(f"📝 Raw length: {len(article_text)}")
print(f"📝 Raw first 800 chars:\n{article_text[:800]}")
print(f"📝 Raw last 400 chars:\n{article_text[-400:]}")

# Step 1: strip outermost ``` fences only
# Strategy: if starts with ```, strip opening fence line.
# For closing, scan from END backwards to find the LAST ``` that is on its own line.
if article_text.startswith('```'):
    first_nl = article_text.find('\n')
    if first_nl != -1:
        article_text = article_text[first_nl+1:]
    else:
        article_text = article_text[3:]
    
    # Strip trailing ``` only if it's the last non-whitespace content
    stripped = article_text.rstrip()
    if stripped.endswith('```'):
        article_text = stripped[:-3].rstrip()
    
    article_text = article_text.strip()
    print(f"📝 After fence strip: {len(article_text)} chars")

# Step 2: if article starts with '{' or '[' (JSON), extract from known fields
if article_text.startswith('{') or article_text.startswith('['):
    print("📝 Detected JSON response, attempting to extract fields...")
    import json as json_mod
    try:
        obj = json_mod.loads(article_text)
        if isinstance(obj, dict):
            # Try to reconstruct as markdown front matter + body
            title = obj.get('title', obj.get('Title', ''))
            date_str = obj.get('date', obj.get('Date', today))
            slug = obj.get('slug', obj.get('Slug', ''))
            tags = obj.get('tags', obj.get('Tags', [category]))
            desc = obj.get('description', obj.get('Description', ''))
            body = obj.get('body', obj.get('Body', obj.get('content', obj.get('Content', ''))))
            
            if body:
                article_text = f"---\ntitle: \"{title}\"\ndate: {date_str}\nslug: \"{slug}\"\ndraft: false\ntags: {json_mod.dumps(tags)}\ndescription: \"{desc}\"\n---\n\n{body}"
                print(f"📝 Reconstructed from JSON: {len(article_text)} chars")
    except Exception as e:
        print(f"📝 JSON parse failed: {e}")

# Step 3: if still no '---', search for front matter markers
if not article_text.startswith('---'):
    fm_start = article_text.find('\n---\n')
    if fm_start == -1:
        fm_start = article_text.find('---')
    if fm_start != -1:
        article_text = article_text[fm_start:].strip()
        print(f"📝 Located front matter at offset {fm_start}")

# Step 3.5: remove stray ``` between frontmatter closing --- and body
# Mistral sometimes outputs: ---\n```\n real body ... despite "No code blocks" in prompt
article_text = re.sub(r'(---)\n```\n', r'\1\n', article_text, count=1)

# Step 4: trim trailing junk after article
article_text = article_text.strip()

print(f"📝 Cleaned article length: {len(article_text)}")

# Step 5: validate body content
parts = article_text.split('---', 2)
if len(parts) < 3:
    print(f"⚠️ Missing front matter closure (---). Raw preview:")
    print(article_text[:500])
    print("⛔ Skipping.")
    exit(1)

fm = parts[1]
body_only = parts[2].strip()

print(f"📝 Front matter: {len(fm)} chars")
print(f"📝 Body: {len(body_only)} chars")

if len(body_only) < 100:
    print(f"⚠️ Article body too short ({len(body_only)} chars).")
    print("--- RAW RESPONSE (first 500) ---")
    print(article_text[:500])
    print("--- RAW RESPONSE (last 500) ---")
    print(article_text[-500:])
    print("⛔ Skipping this generation.")
    exit(1)

# ========== 确保 front matter 包含 description ==========
def ensure_description(text, keyword, today):
    """Auto-fill a reasonable default description if front matter is missing one"""
    parts = text.split('---', 2)
    if len(parts) >= 3:
        fm = parts[1]
        body = parts[2]
        # Check if description field exists and is not empty
        desc_match = re.search(r'^description:\s*(.*)$', fm, re.MULTILINE)
        if not desc_match or not desc_match.group(1).strip():
            # Missing or empty, insert default description
            default_desc = f"In-depth comparison and review of {keyword}. Expert analysis, pricing, features, and recommendations for 2026."
            if desc_match:
                # 替换空描述
                fm = re.sub(r'^description:\s*.*$', f'description: "{default_desc}"', fm, flags=re.MULTILINE)
            else:
                # 在 slug 或 tags 之后添加
                fm = fm.rstrip() + f'\ndescription: "{default_desc}"'
            text = f"---{fm}---\n{body}"
    return text

article_text = ensure_description(article_text, keyword, today)

# ========== 兜底元数据(如果完全没有 front matter)==========
if not article_text.startswith('---'):
    slug = re.sub(r'[^a-z0-9]+', '-', keyword.strip().lower())[:50]
    header = f"""---
title: "Deep Dive: {keyword.title()}"
date: {today}
slug: "{slug}"
draft: false
tags: ["{category}"]
description: "In-depth analysis of {keyword}."
---
"""
    article_text = header + "\n" + article_text

slug_part = re.sub(r'[^a-z0-9]+', '-', keyword.strip().lower())[:50]
filename = f"{today}-{slug_part}.md"
filepath = os.path.join("content", "posts", filename)

os.makedirs(os.path.dirname(filepath), exist_ok=True)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(article_text)

print(f"📌 Current keyword: {keyword}")
print(f"📌 Next index: {next_index}")
print(f"✅ Article generated: {filepath}")

# ========== IndexNow 提交 ==========
def submit_indexnow(article_url):
    if not INDEXNOW_KEY:
        print("⚠️ INDEXNOW_KEY not set, skipping IndexNow submission.")
        return
    url = f"https://www.bing.com/indexnow?url={article_url}&key={INDEXNOW_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code in [200, 202]:
            print(f"✅ IndexNow submitted: {article_url} (status {r.status_code})")
        else:
            print(f"⚠️ IndexNow returned status {r.status_code}")
    except Exception as e:
        print(f"❌ IndexNow submission failed: {e}")

article_url = f"{SITE_URL}/posts/{slug_part}/"
submit_indexnow(article_url)
