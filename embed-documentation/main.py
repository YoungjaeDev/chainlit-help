import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def delete_all_files():
    confirmation = input("This will delete all OpenAI files with purpose 'assistants'.\n Type 'YES' to confirm: ")
    if confirmation == "YES":
        response = await client.files.list(purpose="assistants")
        for file in response.data:
            await client.files.delete(file.id)
        print("All files with purpose 'assistants' have been deleted.")
    else:
        print("Operation cancelled.")

async def create_file(file_path):
    # Handle local file path
    try:
        with open(file_path, "rb") as file_content:
            result = await client.files.create(
                file=file_content,
                purpose="assistants"
            )
            
            file_id = result.id
            print(f"✅ Uploaded {file_id} for {file_path}")
            
            vector_result = await client.vector_stores.files.create(
                vector_store_id=os.environ.get("OPENAI_VECTOR_STORE_ID"),
                file_id=file_id
            )
            print(f"✅ Vectorized {vector_result.id} for {file_path}")
            return file_id
    except Exception as e:
        print(f"❌ ERROR in create_file function: {type(e).__name__}: {str(e)}")
        raise e

async def process_directory(directory, semaphore):
    tasks = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            tasks.append(process_file(file_path, semaphore))
    
    return await asyncio.gather(*tasks)

async def process_file(file_path, semaphore):
    async with semaphore:
        try:
            print(f"Processing: {file_path}")
            await create_file(file_path)
            return f"Successfully processed {file_path}"
        except Exception as e:
            return f"Error processing {file_path}: {str(e)}"

async def main():
    
    await delete_all_files()
    
    # Create a semaphore to limit concurrent tasks to 10
    semaphore = asyncio.Semaphore(10)
    
    # Process both directories
    directories = ['cookbooks', 'documentation']
    tasks = []
    
    for directory in directories:
        if os.path.exists(directory):
            print(f"Processing directory: {directory}")
            tasks.append(process_directory(directory, semaphore))
        else:
            print(f"Directory not found: {directory}")
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Print summary
    print("\nProcessing complete!")
    for result in results:
        if isinstance(result, Exception):
            print(f"Error: {str(result)}")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())