"""Instagram Engagement Automation Platform (deterministic, rule-first).

A separate subsystem alongside the carousel Studio. Turns Instagram comments and
DMs into automated, rule-based actions (reply / send-DM / tag lead) with NO AI in
the core path. AI is an optional response mode added later behind ResponseProvider.

Modules:
  rules   - pure deterministic rule engine (conditions, matching, template vars)
  store   - persistence (workspaces, accounts, posts, comments, conversations,
            messages, rules, executions, events, insights, audit)
  service - Instagram Graph API client for comments/DMs/insights (live Meta)
  api     - REST endpoints + Meta webhook receiver
"""
