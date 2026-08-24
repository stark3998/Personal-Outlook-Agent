"""Intelligence layer — LLM access isolated behind :class:`LLMProvider`.

The Outlook providers never import this package. Intelligence consumes domain models
produced by the Outlook services and treats all email-derived text as untrusted.
"""
