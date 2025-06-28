#!/usr/bin/env python3
"""
Test script to verify Supabase database connection and run the migration
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test the database connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    try:
        print(f"🔗 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        # Test the connection
        result = await conn.fetchval("SELECT version()")
        print(f"✅ Connected successfully!")
        print(f"📝 PostgreSQL version: {result}")
        
        # Test basic query
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        print(f"\n📊 Found {len(tables)} tables in public schema:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def run_basic_migration():
    """Run a basic migration to create the campaigns table"""
    database_url = os.getenv("DATABASE_URL")
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Create campaigns table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                product_name VARCHAR(255) NOT NULL,
                target_audience TEXT NOT NULL,
                headline TEXT,
                primary_text TEXT,
                description TEXT,
                image_path VARCHAR(500),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        print("✅ Basic campaigns table created successfully")
        
        # Insert a test record
        campaign_id = await conn.fetchval("""
            INSERT INTO campaigns (product_name, target_audience, headline, primary_text, description)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, 
        "Test Product", 
        "Tech enthusiasts", 
        "Revolutionary AI Solution", 
        "Discover the future of technology with our cutting-edge AI platform.",
        "Transform your business with intelligent automation."
        )
        
        print(f"✅ Test campaign created with ID: {campaign_id}")
        
        # Query the test record
        campaign = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
        print(f"📝 Retrieved campaign: {campaign['product_name']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

async def test_api_connection():
    """Test connection to the FastAPI server"""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000/")
            if response.status_code == 200:
                print("✅ FastAPI server is running and responding")
                
                # Test the docs endpoint
                docs_response = await client.get("http://127.0.0.1:8000/docs")
                if docs_response.status_code == 200:
                    print("✅ API documentation is accessible")
                
                return True
            else:
                print(f"❌ FastAPI server returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Failed to connect to FastAPI server: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting AdTao Campaign System Tests\n")
    
    # Test 1: Database connection
    print("1️⃣ Testing Database Connection:")
    db_success = await test_connection()
    print()
    
    if db_success:
        # Test 2: Basic migration
        print("2️⃣ Testing Basic Migration:")
        migration_success = await run_basic_migration()
        print()
    
    # Test 3: API connection
    print("3️⃣ Testing API Connection:")
    api_success = await test_api_connection()
    print()
    
    # Summary
    print("📋 Test Summary:")
    print(f"   Database Connection: {'✅ PASS' if db_success else '❌ FAIL'}")
    if db_success:
        print(f"   Database Migration:  {'✅ PASS' if migration_success else '❌ FAIL'}")
    print(f"   API Connection:      {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if db_success and api_success:
        print("\n🎉 All tests passed! Your AdTao Campaign system is ready to use.")
        print("\n📚 Next steps:")
        print("   1. Run the full migration script in Supabase SQL editor: supabase_migration.sql")
        print("   2. Start using the MCP server: python3 mcp_server.py")
        print("   3. Access API docs: http://127.0.0.1:8000/docs")
    else:
        print("\n⚠️ Some tests failed. Please check your configuration.")

if __name__ == "__main__":
    asyncio.run(main()) 