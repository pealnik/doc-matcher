# PDF Compliance Checker

A full-stack web application to check if a PDF document complies with a set of guidelines using Retrieval-Augmented Generation (RAG) and Large Language Models.

## Features

- **Modern Web Interface**: Easy-to-use interface built with React for uploading documents and viewing compliance reports.
- **Powerful FastAPI Backend**: A robust Python backend handles asynchronous processing of large documents.
- **Hybrid Compliance Checking**: Uses a fixed, pre-generated checklist for deterministic analysis combined with RAG for semantic evidence retrieval from the document.
- **Detailed Reporting**: Generates comprehensive reports detailing compliant and non-compliant items with specific evidence.
- **Real-time Progress**: Monitor the compliance check status live in the UI.

## Project Structure

The project is a monorepo containing the `backend` and `client` applications.

```
doc-match/
├── backend/                  # FastAPI application
│   ├── main.py               # API server entrypoint
│   ├── services.py           # Core application logic
│   ├── requirements.txt      # Python dependencies
│   └── ...
├── client/                   # React frontend
│   ├── src/App.tsx           # Main React component
│   ├── package.json          # Node.js dependencies
│   └── ...
├── docker-compose.yml        # Docker configuration
└── README.md                 # This file
```

## Setup and Running the Application

### 1. Prerequisites

- Python 3.8+ and `pip`
- Node.js and `npm`
- An OpenAI API key (for embeddings and/or compliance checks)

### 2. Backend Setup

First, set up and run the FastAPI server.

```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables by copying the example file
cp .env.example .env

# Edit the .env file and add your API keys (e.g., OPENAI_API_KEY)
nano .env

# Run the backend server
uvicorn main:app --reload
```
The backend will now be running on `http://localhost:8000`.

### 3. Frontend Setup

In a new terminal, set up and run the React client.

```bash
# Navigate to the client directory
cd client

# Install Node.js dependencies
npm install

# Run the frontend development server
npm run dev
```
The frontend will now be running on `http://localhost:5173` (or another port if 5173 is busy). You can access the application in your browser at this address.

### Using Docker Compose (Alternative)

Alternatively, you can build and run the entire application using Docker Compose. Ensure you have configured the `backend/.env` file first.

```bash
# From the project root directory:
docker-compose up --build
```

## Architecture

This project uses a full-stack architecture with a Python/FastAPI backend and a React frontend. Its workflow is divided into two distinct phases: an offline **Checklist Generation** step and an online **Compliance Checking** engine.

```mermaid
graph TD
    subgraph "Phase 1: Offline Checklist Generation (Admin Task)"
        A[Regulatory PDF e.g., MEPC.379(80)] -- "1. Extract Text" --> B(Checklist Generation Script);
        B -- "2. Use LLM to Extract & Enrich" --> C[requirements_database.json];
    end

    subgraph "Phase 2: Online Compliance Check (User Workflow)"
        subgraph "Client (Browser)"
            D[React Frontend]
        end
        subgraph "Backend (FastAPI Server)"
            E[API Endpoints]
            F[Hybrid Checklist Checker]
            G((Report Vectorstore))
        end
        C -- "3. Load Fixed Checklist" --> F;
        D -- "4. User Uploads Report PDF" --> E;
        E -- "5. Start Async Task" --> F;
        F -- "6. Index Report into Vectorstore" --> G;
        F -- "7. For each requirement..." --> F;
        F -- "8. Retrieve relevant context from report" --> G;
        F -- "9. Use LLM to check compliance" --> F;
        F -- "10. Send real-time progress" --> D;
        F -- "11. Store Final Report" --> E;
        E -- "12. User downloads report" --> D;
    end
```

### How it Works

#### 1. Offline: Checklist Generation

Before the main application can be used, a structured `requirements_database.json` file must be created. This is a one-time, offline process performed by an administrator using the `generate_checklist_from_mepc.py` script.

1.  **PDF Processing**: The script takes a regulatory document (e.g., an MEPC guideline PDF) as input.
2.  **LLM-Powered Extraction & Enrichment**: It uses a Large Language Model (LLM) to read the document and perform two key actions:
    *   **Extract**: It identifies and pulls out all specific compliance requirements.
    *   **Enrich**: For each requirement, it uses the LLM again to add crucial metadata, such as the compliance `category`, `severity`, `search_keywords`, and `expected_fields`.
3.  **Output**: The script outputs the `requirements_database.json` file. This file acts as the definitive, fixed checklist for the entire system, ensuring that every compliance check is comprehensive and deterministic.

#### 2. Online: Compliance Checking

This is the live workflow when a user interacts with the web application.

1.  **Upload**: A user uploads a report document (e.g., a Ship Recycling Plan) through the React frontend.
2.  **Initiate Task**: The FastAPI backend receives the file and starts an asynchronous task using the `HybridFixedChecklistChecker`, which immediately loads the master `requirements_database.json`.
3.  **Index Report**: The checker creates an in-memory vectorstore from the content of the user's uploaded report. This makes the entire report semantically searchable.
4.  **Iterative Checking (RAG)**: The engine iterates through *every single requirement* from the checklist. For each one, it performs a **Retrieval-Augmented Generation (RAG)** step:
    *   **Retrieve**: It searches the report's vectorstore to find the most relevant text chunks related to the current requirement.
    *   **Augment & Generate**: It sends the requirement and the retrieved text chunks to an LLM, asking it to make a compliance judgment (`Compliant`, `Non-Compliant`, etc.) and provide the specific evidence from the text.
5.  **Track Progress & Deliver Results**: The frontend UI is updated in real-time as each requirement is checked. Once complete, a final, detailed report is generated and made available to the user.

## License

Provided as-is for compliance checking.
