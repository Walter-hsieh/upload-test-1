from langchain_openai import ChatOpenAI 

from langchain_community.document_loaders import PyPDFLoader
from langchain.prompts.chat import ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser



from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit upload size to 16MB

# Ensure the upload and download folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_pdf(api_key, model_name, filename):
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Load and split the PDF into pages
    loader = PyPDFLoader(pdf_path)
    documents = loader.load_and_split()
    
    # Concatenate the content of the documents
    context = " ".join([page.page_content for page in documents])
    if len(context) > 128000:
        context = context[:128000]
    
    # Initialize the appropriate LLM

    model_name = 'gpt-4o-mini'

    llm = ChatOpenAI(temperature=0, model_name=model_name, openai_api_key=api_key)

    user_input = '''Based on the file provided, generate a file name in this format: [year published]_[aspect of the technology]_[main topic]_[primary application].pdf. 
    Please do not give any response except for the file name. Do not include symbols like /, \\, ~, !, @, #, or $ in the file name.'''
    

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", 'You are a helpful assistant. Use the following context when responding:\n\n{context}.'),
        ("human", "{question}")
    ])

    output_parser = StrOutputParser()
    rag_chain = rag_prompt | llm | StrOutputParser()


    response = rag_chain.invoke({
            "question": user_input,
            "context": context
        })
    
    # Extract the filename from the response
    new_filename = response.strip()
    
    # Ensure the filename is secure and ends with .pdf
    new_filename = secure_filename(new_filename)
    if not new_filename.lower().endswith('.pdf'):
        new_filename += '.pdf'
    new_filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], new_filename)
    
    # Handle duplicate filenames
    if os.path.exists(new_filepath):
        base, ext = os.path.splitext(new_filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        new_filename = f"{base}_{timestamp}{ext}"
        new_filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], new_filename)
        print(f"Saving file to: {new_filepath}")
    
    # Move the processed file to the processed folder with the new name
    os.rename(pdf_path, new_filepath)
    return new_filename

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if the request has the file part
        if 'file' not in request.files:
            return 'No file part in the request', 400
        file = request.files['file']
        # If no file is selected
        if file.filename == '':
            return 'No selected file', 400
        if file and allowed_file(file.filename):
            # Secure the filename and save it
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)


            # Get API key and model from the form
            api_key = request.form['api_key']
            model_name = 'gpt-4o-mini'

            
            # Rename the file
            new_filename = process_pdf(api_key, model_name, filename)
            # download_path = os.path.join(app.config['DOWNLOAD_FOLDER'], new_filename)
            # os.rename(upload_path, download_path)
            # Redirect to the download link
            return redirect(url_for('download_file', filename=new_filename))
        else:
            return 'File type not allowed', 400
    return render_template('upload.html')

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'],
                               filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
