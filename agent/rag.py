import json
import os
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
load_dotenv()

def load_documents():
    docs = []
    files = (
        "data/analysts_report.json",
        "data/macro_events.json",
        "data/sector_summaries.json"
    )

    for file in files:
        with open(file,"r") as f:
            data = json.load(f)
        
        for item in data:
            text = json.dumps(item,indent=2)

            docs.append(
                Document(
                    page_content=text,
                    metadata = {"source": file}
                )
            )
    return docs
    
# ---------- CREATE VECTOR STORE ----------
##because currently the docs are small so we have not performed any chunking
def create_vectorstore():
    docs = load_documents()
    embeddings = OpenAIEmbeddings(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    vectorStore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory="./vectorstore"
    )
    vectorStore.persist()
    return vectorStore

# ---------- RETRIEVER ----------
def get_retriever():
    embeddings = OpenAIEmbeddings(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    vectorStore = Chroma(
        persist_directory="./vectorstore",
        embedding_function=embeddings
    )
    retriever = vectorStore.as_retriever(
        search_kwargs={"k":3}
    )
    return retriever




