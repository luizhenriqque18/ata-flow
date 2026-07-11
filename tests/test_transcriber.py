from transcriber import LocalTranscriber

def test_deduplicate_exact_overlap():
    prev = "esta é uma frase de teste com sobreposição"
    curr = "teste com sobreposição e continua assim"
    
    result = LocalTranscriber.deduplicate(prev, curr)
    
    assert result == "e continua assim"

def test_deduplicate_no_overlap():
    prev = "esta é uma frase"
    curr = "outra frase diferente"
    
    result = LocalTranscriber.deduplicate(prev, curr)
    
    assert result == "outra frase diferente"

def test_deduplicate_partial():
    prev = "olá bom dia"
    curr = "dia tudo bem"
    
    result = LocalTranscriber.deduplicate(prev, curr)
    assert result == "tudo bem"

