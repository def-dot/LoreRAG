"""
测试原生 Transformers Tokenizer，获取字符串的 token 数

运行: python examples/test_tokenizer.py
"""
from pydoc import text
from transformers import AutoTokenizer


# 加载分词器
tokenizer = AutoTokenizer.from_pretrained("./hub/bge-m3")

max_tokens = tokenizer.model_max_length
print(f"Tokenizer max tokens: {max_tokens}, embedding max tokens is 256")

text = '''[章节上下文: Root]
Fig. 4. Anodic and cathodic polarization curve of stainless steel in 0.5 M H2SO4 solution in the presence and absence of ES.
'''
tokens = tokenizer.tokenize(text)
        
print(f"  text=[{text}]")
print(f"  text length: {len(text)} chars")
print(f"  token 数: {len(set(tokens))}")
print(f"  实际 tokens: {tokens}")
print()
