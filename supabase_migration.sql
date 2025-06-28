-- AdTao Campaign Database Migration for Supabase
-- Run this script in your Supabase SQL editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create campaigns table
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_name VARCHAR(255) NOT NULL,
    target_audience TEXT NOT NULL,
    headline TEXT,
    primary_text TEXT,
    description TEXT,
    image_path VARCHAR(500),
    image_prompt TEXT,
    tone VARCHAR(50) DEFAULT 'professional',
    ad_length VARCHAR(20) DEFAULT 'medium',
    key_benefits JSONB,
    brand_profile_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create brand_profiles table
CREATE TABLE IF NOT EXISTS brand_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    description TEXT NOT NULL,
    tone_of_voice VARCHAR(100) NOT NULL,
    brand_values JSONB,
    target_audience TEXT NOT NULL,
    visual_identity TEXT NOT NULL,
    color_palette VARCHAR(500),
    do_guidelines JSONB,
    dont_guidelines JSONB,
    slogan VARCHAR(500),
    hashtags JSONB,
    examples TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create images table
CREATE TABLE IF NOT EXISTS generated_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL,
    revised_prompt TEXT,
    file_path VARCHAR(500) NOT NULL,
    static_path VARCHAR(500) NOT NULL,
    width INTEGER,
    height INTEGER,
    size_info VARCHAR(50),
    model VARCHAR(50) NOT NULL DEFAULT 'dall-e-3',
    campaign_id UUID REFERENCES campaigns(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create ad_copies table
CREATE TABLE IF NOT EXISTS ad_copies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_name VARCHAR(255) NOT NULL,
    target_audience TEXT NOT NULL,
    headline TEXT NOT NULL,
    primary_text TEXT NOT NULL,
    description TEXT NOT NULL,
    tone VARCHAR(50) DEFAULT 'professional',
    ad_length VARCHAR(20) DEFAULT 'medium',
    key_benefits JSONB,
    campaign_id UUID REFERENCES campaigns(id),
    brand_profile_id UUID REFERENCES brand_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create competitor_ads table
CREATE TABLE IF NOT EXISTS competitor_ads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    competitor_name VARCHAR(255) NOT NULL,
    ad_image_path VARCHAR(500) NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    target_audience TEXT,
    analysis_data JSONB,
    positioning TEXT,
    typography TEXT,
    visual_elements JSONB,
    color_scheme TEXT,
    effectiveness_score DECIMAL(3,2),
    is_exemplary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_analyzed TIMESTAMP WITH TIME ZONE
);

-- Create video_jobs table
CREATE TABLE IF NOT EXISTS video_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    prompt TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    video_path VARCHAR(500),
    error_message TEXT,
    campaign_id UUID REFERENCES campaigns(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create audio_files table for TTS
CREATE TABLE IF NOT EXISTS audio_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    text_content TEXT NOT NULL,
    voice VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL DEFAULT 'tts-1',
    speed DECIMAL(3,2) DEFAULT 1.0,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    duration_seconds DECIMAL(6,2),
    campaign_id UUID REFERENCES campaigns(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create integrated_ads table
CREATE TABLE IF NOT EXISTS integrated_ads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id),
    ad_copy_id UUID REFERENCES ad_copies(id),
    image_id UUID REFERENCES generated_images(id),
    video_job_id INTEGER REFERENCES video_jobs(id),
    audio_id UUID REFERENCES audio_files(id),
    product_name VARCHAR(255) NOT NULL,
    target_audience TEXT NOT NULL,
    performance_metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create campaign_analytics table
CREATE TABLE IF NOT EXISTS campaign_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id),
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    cost_per_click DECIMAL(10,4),
    conversion_rate DECIMAL(5,4),
    roi DECIMAL(10,4),
    date_recorded DATE DEFAULT CURRENT_DATE,
    platform VARCHAR(50) DEFAULT 'facebook',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON campaigns(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_product_name ON campaigns(product_name);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand_profile ON campaigns(brand_profile_id);

CREATE INDEX IF NOT EXISTS idx_brand_profiles_name ON brand_profiles(brand_name);
CREATE INDEX IF NOT EXISTS idx_brand_profiles_industry ON brand_profiles(industry);

CREATE INDEX IF NOT EXISTS idx_images_campaign ON generated_images(campaign_id);
CREATE INDEX IF NOT EXISTS idx_images_created_at ON generated_images(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ad_copies_campaign ON ad_copies(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_copies_brand_profile ON ad_copies(brand_profile_id);

CREATE INDEX IF NOT EXISTS idx_competitor_ads_category ON competitor_ads(product_category);
CREATE INDEX IF NOT EXISTS idx_competitor_ads_exemplary ON competitor_ads(is_exemplary);

CREATE INDEX IF NOT EXISTS idx_video_jobs_status ON video_jobs(status);
CREATE INDEX IF NOT EXISTS idx_video_jobs_campaign ON video_jobs(campaign_id);

CREATE INDEX IF NOT EXISTS idx_audio_files_campaign ON audio_files(campaign_id);

CREATE INDEX IF NOT EXISTS idx_integrated_ads_campaign ON integrated_ads(campaign_id);

CREATE INDEX IF NOT EXISTS idx_analytics_campaign ON campaign_analytics(campaign_id);
CREATE INDEX IF NOT EXISTS idx_analytics_date ON campaign_analytics(date_recorded DESC);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON campaigns 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_brand_profiles_updated_at BEFORE UPDATE ON brand_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integrated_ads_updated_at BEFORE UPDATE ON integrated_ads 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_jobs_updated_at BEFORE UPDATE ON video_jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS) for better security
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_copies ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrated_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_analytics ENABLE ROW LEVEL SECURITY;

-- Create policies (allowing all operations for now - adjust based on your auth needs)
CREATE POLICY "Allow all operations on campaigns" ON campaigns FOR ALL USING (true);
CREATE POLICY "Allow all operations on brand_profiles" ON brand_profiles FOR ALL USING (true);
CREATE POLICY "Allow all operations on generated_images" ON generated_images FOR ALL USING (true);
CREATE POLICY "Allow all operations on ad_copies" ON ad_copies FOR ALL USING (true);
CREATE POLICY "Allow all operations on competitor_ads" ON competitor_ads FOR ALL USING (true);
CREATE POLICY "Allow all operations on video_jobs" ON video_jobs FOR ALL USING (true);
CREATE POLICY "Allow all operations on audio_files" ON audio_files FOR ALL USING (true);
CREATE POLICY "Allow all operations on integrated_ads" ON integrated_ads FOR ALL USING (true);
CREATE POLICY "Allow all operations on campaign_analytics" ON campaign_analytics FOR ALL USING (true);

-- Insert some sample data for testing
INSERT INTO brand_profiles (brand_name, industry, description, tone_of_voice, brand_values, target_audience, visual_identity) VALUES
('TechStart Inc', 'Technology', 'Innovative startup focused on AI solutions', 'professional', 
 '["innovation", "reliability", "user-friendly"]', 'Tech-savvy professionals aged 25-45', 
 'Modern, clean design with blue and white color scheme')
ON CONFLICT DO NOTHING;

-- Create a view for campaign summary
CREATE OR REPLACE VIEW campaign_summary AS
SELECT 
    c.id,
    c.product_name,
    c.target_audience,
    c.headline,
    c.created_at,
    bp.brand_name,
    bp.industry,
    COUNT(gi.id) as image_count,
    COUNT(ac.id) as copy_count,
    COUNT(vj.id) as video_count,
    COUNT(af.id) as audio_count
FROM campaigns c
LEFT JOIN brand_profiles bp ON c.brand_profile_id = bp.id
LEFT JOIN generated_images gi ON c.id = gi.campaign_id
LEFT JOIN ad_copies ac ON c.id = ac.campaign_id
LEFT JOIN video_jobs vj ON c.id = vj.campaign_id
LEFT JOIN audio_files af ON c.id = af.campaign_id
GROUP BY c.id, c.product_name, c.target_audience, c.headline, c.created_at, bp.brand_name, bp.industry
ORDER BY c.created_at DESC;

-- Grant necessary permissions to the authenticated role
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO authenticated; 