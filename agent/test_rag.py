from agent.rag import get_retriever

retirever = get_retriever()

query = "What do analysts think about Infosys?"

docs = retirever.invoke(query)

for doc in docs:
    print("\n")
    print(doc.page_content)