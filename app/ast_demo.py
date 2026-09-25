import ast

code = """
def create_order():
    process_payment()
"""

tree = ast.parse(code)

print(ast.dump(tree, indent=4))