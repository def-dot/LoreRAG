import pdfplumber

with pdfplumber.open("./table.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)

"""
['姓名', '年级', '身高']
['sdf', '101', '130']
['df', '101', '140']
"""