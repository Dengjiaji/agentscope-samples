Analyst Signal Summary:
{{analyst_signals}}

Please decide whether communication is needed and explain the reason. If communication is needed, please specify:
- Communication type (private_chat or meeting)
- Target analyst list (for private_chat: only one analyst, for meeting: multiple analysts)
- Discussion topic
- Selection reason

Return JSON format:
{
  "should_communicate": true/false,
  "communication_type": "private_chat" or "meeting",
  "target_analysts": ["analyst1"] (for private_chat) or ["analyst1", "analyst2"] (for meeting),
  "discussion_topic": "discussion topic",
  "reasoning": "selection reason"
}

