"""
测试原生 Transformers Tokenizer，获取字符串的 token 数

运行: python examples/test_tokenizer.py
"""
from pydoc import text
from transformers import AutoTokenizer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# 加载分词器
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, model_max_length=256)

max_tokens = tokenizer.model_max_length
print(f"Tokenizer max tokens: {max_tokens}, embedding max tokens is 256")

text = 'Table 1 Potentiodynamic polarization data for stainless steel in the absence and presence of ES in 0.5 M H2SO4 solution.\n0, bc (V/dec) = 0.0335. 0, ba (V/dec) = 0.0409. 0, Ecorr (V) = \x00 0.9393. 0, icorr (A/cm 2 ) = 0.0003. 0, Polarization resistance ( Ω ) = 24.0910. 0, Corrosion rate (mm/year) = 2.8163. 2, bc (V/dec) = 1.9460. 2, ba (V/dec) = 0.0596. 2, Ecorr (V) = \x00 0.8276. 2, icorr (A/cm 2 ) = 0.0002. 2, Polarization resistance ( Ω ) = 121.440. 2, Corrosion rate (mm/year) = 1.5054. 4, bc (V/dec) = 0.0163. 4, ba (V/dec) = 0.2369. 4, Ecorr (V) = \x00 0.8825. 4, icorr'
tokens = tokenizer.tokenize(text)
        
print(f"  text=[{text}]")
print(f"  text length: {len(text)} chars")
print(f"  token 数: {len(tokens)}")
print(f"  实际 tokens: {tokens}")
print()
