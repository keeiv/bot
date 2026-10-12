"""English and Traditional Chinese copy for ticket."""

MESSAGES: dict[str, dict[str, str]] = {
    "ticket.close_ticket": {"en": "Close ticket", "zh": "關閉工單"},
    "ticket.ticket": {"en": "ticket-{v0:04d}-{v1}", "zh": "工單-{v0:04d}-{v1}"},
    "ticket.closure_reason": {"en": "Closure reason", "zh": "關閉原因"},
    "ticket.enter_a_reason_for_closing_the": {
        "en": "Enter a reason for closing the ticket…",
        "zh": "請輸入關閉工單的原因...",
    },
    "ticket.close_with_reason": {"en": "Close with reason", "zh": "有原因關閉工單"},
    "ticket.open_ticket": {"en": "Open ticket", "zh": "開啟工單"},
    "ticket.closed_ticket_closed": {
        "en": "[Closed] Ticket closed",
        "zh": "[關閉] 工單已關閉",
    },
    "ticket.this_ticket_was_closed_by": {
        "en": "This ticket was closed by {v0}",
        "zh": "此工單已由 {v0} 關閉",
    },
    "ticket.ticket_id": {"en": "Ticket ID: {v0}", "zh": "工單ID: {v0}"},
    "ticket.ticket_new_ticket_created": {
        "en": "[Ticket] New ticket created",
        "zh": "[工單] 新工單已建立",
    },
    "ticket.describe_the_issue_in_detail_staff": {
        "en": "Describe the issue in detail. Staff will respond in this thread.",
        "zh": "請詳細說明你的問題，工作人員會盡快回覆。",
    },
    "ticket.created_by": {"en": "Created by", "zh": "建立者"},
    "ticket.ticket_number": {"en": "Ticket number", "zh": "工單編號"},
    "ticket.ticket_id_server": {
        "en": "Ticket ID: {v0} | Server: {v1}",
        "zh": "工單ID: {v0} | 伺服器: {v1}",
    },
    "ticket.success_ticket_created": {
        "en": "[Success] Ticket created: {v0}",
        "zh": "[成功] 已建立工單: {v0}",
    },
    "ticket.tickets_support_tickets": {
        "en": "[Tickets] Support tickets",
        "zh": "[工單] 支援工單系統",
    },
    "ticket.use_the_button_below_to_open": {
        "en": "Use the button below to open a support ticket.\nStaff will respond in a private thread.",
        "zh": "如果你需要協助，請點擊下方按鈕開啟工單。\n工作人員會在私人討論串中回覆你。",
    },
    "ticket.success_ticket_system_configured": {
        "en": "[Success] Ticket system configured",
        "zh": "[成功] 工單系統已設定",
    },
    "ticket.ticket_channel_staff_role_panel_message": {
        "en": "Ticket channel: {v0}\nStaff role: {v1}\nPanel message ID: {v2}",
        "zh": "工單頻道: {v0}\n通知身份組: {v1}\n面板訊息ID: {v2}",
    },
    "ticket.failed_this_command_is_only_available": {
        "en": "[Failed] This command is only available in a ticket thread",
        "zh": "[失敗] 此指令只能在工單討論串中使用",
    },
    "ticket.failed_only_staff_or_the_ticket": {
        "en": "[Failed] Only staff or the ticket creator can close a ticket",
        "zh": "[失敗] 只有管理員或工單建立者可以關閉工單",
    },
    "ticket.failed_the_ticket_system_is_not": {
        "en": "[Failed] The ticket system is not configured",
        "zh": "[失敗] 工單系統尚未設定",
    },
    "ticket.failed_an_open_ticket_already_exists": {
        "en": "[Failed] An open ticket already exists: <#{v0}>",
        "zh": "[失敗] 你已有一個開啟中的工單: <#{v0}>",
    },
    "ticket.the_ticket_panel_must_be_in": {
        "en": "The ticket panel must be in a text channel.",
        "zh": "工單面板必須位於文字頻道。",
    },
    "ticket.info_syntax_ticket_setup_channel_role": {
        "en": "[Info] Syntax: `>>>ticket setup <#channel> <@role>`",
        "zh": "[提示] 使用方式: `>>>ticket setup <#頻道> <@身份組>`",
    },
    "ticket.failed_provide_a_channel_and_role": {
        "en": "[Failed] Provide a channel and role\nSyntax: `>>>ticket setup <#channel> <@role>`",
        "zh": "[失敗] 請提供頻道和身份組\n使用方式: `>>>ticket setup <#頻道> <@身份組>`",
    },
    "ticket.failed_everyone_cannot_be_used_for": {
        "en": "[Failed] @everyone cannot be used for ticket notifications\nCreate a dedicated staff role",
        "zh": "[失敗] 無法使用 @everyone 作為工單通知身份組\n請建立專用的工作人員身份組",
    },
    "ticket.failed_the_bot_lacks_send_messages": {
        "en": "[Failed] The bot lacks Send Messages or Create Private Threads in {v0}",
        "zh": "[失敗] 機器人在 {v0} 中缺少「發送訊息」或「建立私人討論串」權限",
    },
    "ticket.failed_the_bot_cannot_create_private": {
        "en": "[Failed] The bot cannot create private threads",
        "zh": "[失敗] 機器人權限不足，無法建立私人討論串",
    },
    "ticket.failed_ticket_creation_failed": {
        "en": "[Failed] Ticket creation failed: {v0}",
        "zh": "[失敗] 建立工單失敗: {v0}",
    },
}
