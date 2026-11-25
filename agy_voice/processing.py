"""Processamento de transcrições independente do provedor de reconhecimento de voz."""


def deduplicate(previous_text: str, current_text: str) -> str:
    """Remove o prefixo repetido que coincide com as últimas cinco palavras anteriores."""
    if not previous_text or not current_text:
        return current_text
    previous_words = previous_text.split()[-5:]
    current_words = current_text.split()
    for index in range(len(previous_words)):
        prefix = previous_words[index:]
        if current_words[: len(prefix)] == prefix:
            return " ".join(current_words[len(prefix) :])
    return current_text
