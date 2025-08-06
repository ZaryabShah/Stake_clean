// Simple Provider Fetcher - wrapper for the working graphql_fetcher.js
// Fetches a single provider with specified offset and limit

const { spawn } = require('child_process');
const fs = require('fs');

async function fetchProvider(providerSlug, offset = 0, limit = 39) {
    console.log(`🚀 Fetching ${providerSlug} - offset: ${offset}, limit: ${limit}`);
    
    return new Promise((resolve, reject) => {
        // Call the working graphql_fetcher.js with proper arguments
        const process = spawn('node', ['graphql_fetcher.js', `--provider=${providerSlug}`, `--offset=${offset}`, `--limit=${limit}`], {
            stdio: 'pipe'
        });
        
        let output = '';
        let errorOutput = '';
        
        process.stdout.on('data', (data) => {
            output += data.toString();
            console.log(data.toString().trim());
        });
        
        process.stderr.on('data', (data) => {
            errorOutput += data.toString();
            console.error(data.toString().trim());
        });
        
        process.on('close', (code) => {
            if (code === 0) {
                console.log(`✅ GraphQL fetcher completed successfully`);
                resolve({ success: true, output });
            } else {
                console.error(`❌ GraphQL fetcher failed with code ${code}`);
                reject(new Error(`GraphQL fetcher failed with code ${code}: ${errorOutput}`));
            }
        });
        
        // Timeout after 2 minutes
        setTimeout(() => {
            process.kill();
            reject(new Error('Request timeout after 2 minutes'));
        }, 120000);
    });
}

// Get command line arguments
const args = process.argv.slice(2);
const providerSlug = args[0] || 'pragmatic-play';
const offset = parseInt(args[1]) || 0;
const limit = parseInt(args[2]) || 39;

// Run if called directly
if (require.main === module) {
    fetchProvider(providerSlug, offset, limit)
        .then(() => {
            console.log('🎉 Fetch completed!');
            process.exit(0);
        })
        .catch(error => {
            console.error('💥 Fetch failed:', error.message);
            process.exit(1);
        });
}

module.exports = { fetchProvider };
