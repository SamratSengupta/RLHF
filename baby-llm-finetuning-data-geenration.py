import PyPDF2
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from gensim.models.coherencemodel import CoherenceModel
from gensim.corpora.dictionary import Dictionary
import numpy as np
import os
import json

from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from langchain_openai import AzureChatOpenAI, AzureOpenAI
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from semantic_text_splitter import HuggingFaceTextSplitter,TiktokenTextSplitter
from tokenizers import Tokenizer

#!pip install semantic-text-splitter==0.2.3


os.environ["OPENAI_API_TYPE"] = ""
os.environ["OPENAI_API_VERSION"] = ''
os.environ["AZURE_OPENAI_API_VERSION"] = ''
os.environ["AZURE_OPENAI_ENDPOINT"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["AZURE_OPENAI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"]=""

model_name='gpt-4-1106'
llm_azure = AzureChatOpenAI(model_name=model_name,deployment_name=model_name,
                            temperature=0,model_kwargs = {'seed': 42})
pdf_path='data/nha-heart-module.pdf'
text_splitter = SemanticChunker(AzureOpenAIEmbeddings())


def extract_text_from_pdf(pdf_path):
    pdf_text = "";pdf_text_arr=[]
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:           
            pdf_text += page.extract_text()
            pdf_text_arr.append(page.extract_text())
    return pdf_text,pdf_text_arr
pdf_text,pdf_text_arr = extract_text_from_pdf(pdf_path)


# Maximum number of tokens in a chunk
max_tokens = 1000
splitter = TiktokenTextSplitter("gpt-3.5-turbo", trim_chunks=False)
chunks = splitter.chunks(pdf_text,max_tokens)


qa_prompt = PromptTemplate(
        input_variables=["content", "num_pairs"],
        template="""
        
        Based on the following content, generate {num_pairs} high-quality question-answer pairs. 
        Ensure the questions are standalone and the answers are detailed. 
        
        Vary the questions to include tricky questions, detail-oriented questions, high-level questions,
        application questions, and critical thinking questions.
        
        Content: {content}
        {questions_and_answers}
        
        """
    )
# Create the LLMChain
qa_chain = LLMChain(llm=llm_azure, prompt=qa_prompt)


def generate_multiple_qa_pairs(content, num_pairs):
    questions_and_answers = "\n".join([f"Q{i+1}: \nA{i+1}: \n" for i in range(num_pairs)])
    qa_text = qa_chain.run(content=content, num_pairs=num_pairs,
                           questions_and_answers=questions_and_answers)
    qa_pairs = []
    for i in range(num_pairs):
        question = qa_text.split(f"Q{i+1}:")[1].split(f"A{i+1}:")[0].strip()
        answer = qa_text.split(f"A{i+1}:")[1].split(f"Q{i+2}:")[0].strip() if i+2 <= num_pairs else qa_text.split(f"A{i+1}:")[1].strip()
        qa_pairs.append({"question": question, "answer": answer})
    return qa_pairs


def create_unique_qa_dataset(chunks, total_questions=1200):
    num_chunks = len(chunks)
    n_questions_per_chunk = total_questions // num_chunks
    num_pairs_per_call = 10  # Adjust this number to optimize the LLM calls
    all_qa_pairs = []
    seen_pairs = set()
    
    while len(all_qa_pairs) < total_questions:
        for chunk in chunks:
            qa_pairs = generate_multiple_qa_pairs(chunk, num_pairs_per_call)
            for pair in qa_pairs:
                pair_tuple = (pair['question'], pair['answer'])
                if pair_tuple not in seen_pairs:
                    seen_pairs.add(pair_tuple)
                    all_qa_pairs.append(pair)
                if len(all_qa_pairs) >= total_questions:
                    break
            if len(all_qa_pairs) >= total_questions:
                break
    
    return all_qa_pairs[:total_questions]

qa_dataset = create_unique_qa_dataset(chunks)
print(len(qa_dataset))

with open('data/baby-llm-training-examples.json','w') as json_file:
    json.dump(qa_dataset,json_file,indent=4)