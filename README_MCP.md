# AdTao Campaign MCP Server Setup

## 🚀 Successfully Connected!

Your AdTao Campaign system is now fully integrated with Supabase and ready for MCP (Model Context Protocol) usage.

## ✅ What's Working

### 1. **Database Connection** 
- ✅ Connected to Supabase PostgreSQL database
- ✅ Test campaign created successfully
- ✅ Database operations working properly

### 2. **FastAPI Server**
- ✅ Running on http://127.0.0.1:8000
- ✅ API documentation available at http://127.0.0.1:8000/docs
- ✅ All endpoints accessible

### 3. **MCP Configuration**
- ✅ `mcp.json` configuration file created
- ✅ `mcp_server.py` MCP server implementation ready
- ✅ Database migration script prepared

## 📂 Files Created

### Core MCP Files:
1. **`mcp.json`** - MCP server configuration
2. **`mcp_server.py`** - MCP server implementation 
3. **`supabase_migration.sql`** - Database schema migration
4. **`test_database.py`** - Connection verification script
5. **`.env`** - Environment variables (already configured)

## 🛠 Usage Instructions

### 1. Run Full Database Migration
Copy and paste the contents of `supabase_migration.sql` into your Supabase SQL editor:
```bash
# Open Supabase Dashboard → SQL Editor → New Query
# Copy/paste supabase_migration.sql content and run
```

### 2. Start the MCP Server
```bash
python3 mcp_server.py
```

### 3. Use MCP Tools
The MCP server provides these tools:
- **`execute_sql`** - Run SQL queries on Supabase
- **`call_api_endpoint`** - Call FastAPI endpoints  
- **`create_campaign`** - Create complete ad campaigns
- **`analyze_campaign_performance`** - Analyze campaign data

### 4. Access Resources
- **`adtao://database/tables`** - Database schema info
- **`adtao://api/endpoints`** - Available API endpoints
- **`adtao://campaigns/recent`** - Recent campaigns

## 🔧 Configuration Details

### Environment Variables (Already Set)
```bash
# Azure OpenAI
AZURE_DALLE_KEY=your_dalle_api_key_here
AZURE_GPT_KEY=your_gpt_api_key_here

# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
DATABASE_URL=postgresql://postgres:your_password@db.your-project-id.supabase.co:5432/postgres
```

### Database Tables (Will be created after migration)
- `campaigns` - Main campaign data
- `brand_profiles` - Brand profile information
- `generated_images` - AI-generated images
- `ad_copies` - Ad copy variations
- `competitor_ads` - Competitor analysis
- `video_jobs` - Video generation tasks
- `audio_files` - TTS audio files
- `integrated_ads` - Complete ad campaigns
- `campaign_analytics` - Performance metrics

## 📊 Example MCP Usage

### Create a Campaign via MCP
```json
{
  "tool": "create_campaign",
  "arguments": {
    "product_name": "AI Writing Assistant",
    "target_audience": "Content creators and marketers",
    "key_benefits": ["Save time", "Improve quality", "Scale content"],
    "tone": "professional",
    "generate_image": true
  }
}
```

### Execute SQL via MCP
```json
{
  "tool": "execute_sql", 
  "arguments": {
    "query": "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 5"
  }
}
```

### Call API Endpoint via MCP
```json
{
  "tool": "call_api_endpoint",
  "arguments": {
    "endpoint": "/generate-ad-copy",
    "method": "POST",
    "data": {
      "product_name": "Smart Watch",
      "target_audience": "Fitness enthusiasts"
    }
  }
}
```

## 🚀 Next Steps

1. **Run the full migration** in Supabase SQL editor
2. **Test MCP server** with your preferred MCP client
3. **Create your first campaign** using the MCP tools
4. **Explore the API documentation** at http://127.0.0.1:8000/docs

## 🔍 Monitoring

### Check FastAPI Server Status
```bash
curl http://127.0.0.1:8000/
```

### Verify Database Connection
```bash
python3 test_database.py
```

### View Current Campaigns
```bash
# Via MCP or direct SQL in Supabase dashboard
SELECT * FROM campaigns ORDER BY created_at DESC;
```

## 📞 Support

If you encounter any issues:
1. Check that FastAPI server is running
2. Verify database connection with `test_database.py`
3. Ensure all environment variables are set correctly
4. Check Supabase dashboard for any database issues

---

**🎉 Your AdTao Campaign system with MCP integration is ready to use!** 