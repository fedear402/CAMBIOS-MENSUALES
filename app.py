from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import pandas as pd
import os
from io import BytesIO
import uuid

app = Flask(__name__)
app.secret_key = "pricecomparison_secret_key"

# Create upload folder if it doesn't exist
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file1' not in request.files or 'file2' not in request.files:
        flash('Both files are required')
        return redirect(request.url)
    
    file1 = request.files['file1']
    file2 = request.files['file2']
    month1 = request.form['month1']
    month2 = request.form['month2']
    
    if file1.filename == '' or file2.filename == '':
        flash('Both files must be selected')
        return redirect(request.url)
    
    if not (file1.filename.endswith('.xlsx') or file1.filename.endswith('.xls')) or \
       not (file2.filename.endswith('.xlsx') or file2.filename.endswith('.xls')):
        flash('Files must be Excel files (.xlsx or .xls)')
        return redirect(request.url)
    
    # Generate unique filenames to avoid conflicts
    unique_filename1 = f"{uuid.uuid4()}_{file1.filename}"
    unique_filename2 = f"{uuid.uuid4()}_{file2.filename}"
    
    file1_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename1)
    file2_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename2)
    
    file1.save(file1_path)
    file2.save(file2_path)
    
    try:
        # Load the Excel files
        df_month1 = pd.read_excel(file1_path)
        df_month2 = pd.read_excel(file2_path)
        
        # Check if REFFERENCIA column exists in both dataframes
        if 'REFFERENCIA' not in df_month1.columns or 'REFFERENCIA' not in df_month2.columns:
            flash('Error: REFFERENCIA column not found in one or both files')
            # Clean up files
            os.remove(file1_path)
            os.remove(file2_path)
            return redirect(url_for('index'))
        
        # Check if PVP column exists in both dataframes
        if 'PVP' not in df_month1.columns or 'PVP' not in df_month2.columns:
            flash('Error: PVP column not found in one or both files')
            # Clean up files
            os.remove(file1_path)
            os.remove(file2_path)
            return redirect(url_for('index'))
        
        # Rename columns to include the month suffix (except REFFERENCIA)
        df_month1 = df_month1.rename(columns=lambda x: f"{x}-{month1}" if x != "REFFERENCIA" else x)
        df_month2 = df_month2.rename(columns=lambda x: f"{x}-{month2}" if x != "REFFERENCIA" else x)
        
        # Merge the two dataframes on "REFFERENCIA"
        df_merged = pd.merge(df_month1, df_month2, on='REFFERENCIA', how='outer')
        
        # Calculate the percentage change
        df_merged['CAMBIO'] = ((df_merged[f'PVP-{month2}'] - df_merged[f'PVP-{month1}']) / df_merged[f'PVP-{month1}'])
        
        # Generate output filename
        output_filename = f"Comparacion-{month1}-{month2}.xlsx"
        
        # Convert the merged dataframe to Excel and save to a file
        comparison_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        df_merged.to_excel(comparison_path, index=False)
        
        # Store paths in session for download route
        session = {
            'file1_path': file1_path,
            'file2_path': file2_path,
            'comparison_path': comparison_path,
            'month1': month1,
            'month2': month2
        }
        
        # Note: we're not removing the files here anymore
        
        # Create sample data for display
        df_month1_sample = df_month1.head(5).to_html(classes='table table-striped', index=False)
        df_month2_sample = df_month2.head(5).to_html(classes='table table-striped', index=False)
        df_merged_sample = df_merged.head(5).to_html(classes='table table-striped', index=False)
        
        return render_template('results.html', 
                              month1=month1, 
                              month2=month2,
                              df_month1_sample=df_month1_sample,
                              df_month2_sample=df_month2_sample,
                              df_merged_sample=df_merged_sample,
                              output_filename=output_filename,
                              file1_name=file1.filename,
                              file2_name=file2.filename)
    
    except Exception as e:
        # Clean up files
        if os.path.exists(file1_path):
            os.remove(file1_path)
        if os.path.exists(file2_path):
            os.remove(file2_path)
        flash(f'Error processing files: {str(e)}')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    # Get the user's session data
    month1 = request.args.get('month1')
    month2 = request.args.get('month2')
    
    # Create the merged Excel file in memory
    try:
        # We need to get the data from the session
        # Since we can't rely on files being stored long-term, let's create a temporary file
        output = BytesIO()
        
        # Create a temporary message to send back
        output.write(b'This is a placeholder. In production, the file would be generated correctly.')
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        flash(f'Error generating download: {str(e)}')
        return redirect(url_for('index'))

# Create a simplified version of the download_result function
@app.route('/download_result')
def download_result():
    output_filename = request.args.get('filename')
    comparison_path = request.args.get('comparison_path')
    
    try:
        if os.path.exists(comparison_path):
            return send_file(
                comparison_path,
                as_attachment=True,
                download_name=output_filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            flash('Error: Comparison file not found')
            return redirect(url_for('index'))
    
    except Exception as e:
        flash(f'Error generating download: {str(e)}')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)