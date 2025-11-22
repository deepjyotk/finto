import pandas as pd

# QA
inputs = [
    "What percentage of my portfolio is in each sector?",
    "How much profit did I make in Adani Green?"
]

outputs = [
    "Your portfolio is overwhelmingly concentrated in the **Metals** sector, which makes up **about 91%** of your total portfolio value. This means nearly all your invested capital is tied to one sector, creating a very high concentration risk. The next largest exposure is **Auto Ancillary** at around **6%**, while all other sectors—such as **Textiles, Financial Services, Chemicals, Healthcare, Energy, FMCG, Agriculture, Real Estate, Retail, Media & Entertainment, Telecom, and ETFs**—each contribute **well under 1%** to your overall portfolio. In other words, your investments outside Metals are extremely small and do not meaningfully diversify sector risk. If the heavy focus on Metals is intentional due to your conviction or strategy, this may be acceptable; otherwise, you may want to consider reallocating to achieve better diversification and reduce volatility tied to a single sector’s performance.",
    "You have made **₹649.75** profit in Adani Green.",
]


from langsmith import Client

client = Client()
dataset_name = "finto-qa-dataset-1"

# Store
dataset = client.create_dataset(
    dataset_name=dataset_name,
    description="QA pairs about finto chatbot.",
)
client.create_examples(
    inputs=[{"question": q} for q in inputs],
    outputs=[{"answer": a} for a in outputs],
    dataset_id=dataset.id,
)