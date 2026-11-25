"""Deduplicação de blocos sobrepostos sem carregar nenhum backend de voz."""

import pytest

from agy_voice.processing import deduplicate


@pytest.mark.parametrize(
    "previous, current, expected",
    [
        ("Bom dia a todos nos", "todos nos vamos comecar", "vamos comecar"),
        (
            "esta é uma frase de teste com sobreposição",
            "teste com sobreposição e continua assim",
            "e continua assim",
        ),
        ("olá bom dia", "dia tudo bem", "tudo bem"),
        ("um dois tres", "quatro cinco seis", "quatro cinco seis"),
        ("", "algum texto", "algum texto"),
        ("algum texto", "", ""),
        ("", "", ""),
        ("a decisão foi aprovada", "a decisão foi aprovada", ""),
        ("sim sim", "sim sim vamos", "vamos"),
        ("um dois três quatro cinco seis", "dois três quatro cinco seis fim", "fim"),
    ],
)
def test_deduplicate(previous, current, expected):
    assert deduplicate(previous, current) == expected
