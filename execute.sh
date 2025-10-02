#!/bin/bash
 
# Define the directory where the files are
DATA_DIR="./data/"
VENV_PATH="MAP"
REQUIREMENTS_FILE="MAP/requirements.txt"


if [ ! -d "$VENV_PATH" ]; then
    echo "virtual environment '$VENV_PATH' not found. Creating..."
    python3 -m venv "$VENV_PATH" || { echo "Falha ao criar o ambiente virtual. Verifique a instalação do python3-venv."; exit 1; }
fi

echo "________________________ Activating the Virtual Environment at MAP ________________________"
source $VENV_PATH/bin/activate

if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Verifying and installing requirements in $REQUIREMENTS_FILE..."
    # The command 'pip install -r' is idempotent and only installs what is necessary.
    pip install -r "$REQUIREMENTS_FILE" || { echo "Falha ao instalar os requisitos. Abortando."; deactivate; exit 1; }
else
    echo "WARNING: The requirements file '$REQUIREMENTS_FILE' was not found. Proceeding without forced installation."
fi



ls -A1 "$DATA_DIR" | while IFS= read -r file_name; do # returns only the names of the files in the directory
    # Verify if the variable 'file_name' is not empty.
    if [[ -n "$file_name" ]]; then
        echo "Processing file name: $file_name"
        python3 map_creator.py "$file_name"
    fi
done
        deactivate
        echo "________________________ Deactivating the Virtual Environment at MAP ________________________"
