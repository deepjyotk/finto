from json import load
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonREPLTool
from langchain_core.runnables import RunnableSequence

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm_generate = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Create Python REPL tool
python_tool = PythonREPLTool()

# Step 1: Prompt to generate code
prompt_generate = ChatPromptTemplate.from_template("""
You are a Python expert.
Write Python code to extract the requested data from an Excel file.
The Excel file is located at: {excel_path}
Excel preview (first rows):
{excel_preview}
User request: {user_request}

Your code must:
- Use pandas
- Print the result clearly

Return only the Python code, no explanation.
""")

# Step 2: Chain for code generation
generate_code_chain = prompt_generate | llm_generate | (lambda msg: msg.content)

# Step 3: Combine with REPL for execution
extract_data_chain = RunnableSequence(first=generate_code_chain, last=python_tool)

df = pd.read_excel("portfolio.xlsx")
# Provide a small preview of the dataframe to the LLM as context
excel_preview = df.head().to_string()

# Step 4: Run the chain, passing template variables correctly
result = extract_data_chain.invoke({
    "excel_path": "portfolio.xlsx",
    "excel_preview": excel_preview,
    "user_request": "what is the quantity of usha martin stocks i have currently?",
})

print("✅ Final Output:\n", result)