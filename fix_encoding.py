import sys

try:
    # Try to read the file with UTF-8 encoding
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    print("File can be read with UTF-8 encoding")
    
    # Try to run the app
    print("Attempting to execute app.py...")
    exec(content)
    
except UnicodeDecodeError as e:
    print(f"Unicode error: {e}")
    # Try to read with different encoding and fix
    try:
        with open('app.py', 'r', encoding='latin-1') as f:
            content = f.read()
        
        # Save back with UTF-8 encoding
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("File encoding fixed. Try running again.")
    except Exception as fix_error:
        print(f"Could not fix encoding: {fix_error}")
        
except Exception as e:
    print(f"Other error: {e}")
    import traceback
    traceback.print_exc()