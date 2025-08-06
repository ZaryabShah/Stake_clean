// Complete All Providers with Parallel Processing
// Enhanced version with concurrent requests and robust handling

const { completeProviderParallel } = require('./parallel_provider_completion.js');
const { scanAllProviders } = require('./enhanced_provider_completion.js');

async function completeAllProvidersParallel() {
    console.log('🚀 Starting Enhanced Complete All Providers Script');
    console.log('================================================');
    
    // Scan for incomplete providers
    const allProviders = scanAllProviders();
    const incompleteProviders = allProviders.filter(p => p.remainingGames > 0);
    
    // Sort by remaining games (smallest first for faster completion)
    incompleteProviders.sort((a, b) => a.remainingGames - b.remainingGames);
    
    console.log(`\n📊 Found ${incompleteProviders.length} incomplete providers`);
    console.log(`📊 Total remaining games: ${incompleteProviders.reduce((sum, p) => sum + p.remainingGames, 0)}`);
    
    if (incompleteProviders.length === 0) {
        console.log('🎉 All providers are already complete!');
        return;
    }
    
    console.log('\n📋 Processing order (smallest first):');
    incompleteProviders.forEach((p, i) => {
        console.log(`${i + 1}. ${p.name}: ${p.remainingGames} games remaining (${p.fetchedGames}/${p.totalGames})`);
    });
    
    console.log('\n🔧 Enhanced Features:');
    console.log('• ⚡ Parallel requests (3 concurrent)');
    console.log('• 🎯 Smart offset tracking');
    console.log('• ⏭️ Skip missing games automatically');
    console.log('• 🛑 Stop when provider is complete');
    console.log('• 🔄 Robust retry logic');
    
    // Process each provider
    let completed = 0;
    let failed = 0;
    
    for (let i = 0; i < incompleteProviders.length; i++) {
        const provider = incompleteProviders[i];
        
        console.log(`\n${'='.repeat(80)}`);
        console.log(`📦 Processing ${i + 1}/${incompleteProviders.length}: ${provider.name}`);
        console.log(`📊 ${provider.remainingGames} games remaining (${provider.fetchedGames}/${provider.totalGames})`);
        console.log(`${'='.repeat(80)}`);
        
        const startTime = Date.now();
        
        try {
            const result = await completeProviderParallel(provider);
            const duration = ((Date.now() - startTime) / 1000).toFixed(1);
            
            if (result.success && result.isComplete) {
                completed++;
                console.log(`✅ ${provider.name} completed in ${duration}s! (${result.totalGames} games total)`);
            } else {
                console.log(`⚠️ ${provider.name} partially completed in ${duration}s (${result.totalGames} games fetched)`);
            }
        } catch (error) {
            failed++;
            const duration = ((Date.now() - startTime) / 1000).toFixed(1);
            console.error(`❌ Failed to complete ${provider.name} after ${duration}s: ${error.message}`);
        }
        
        // Progress update
        console.log(`\n📊 Progress: ${i + 1}/${incompleteProviders.length} providers processed`);
        console.log(`📊 Completed: ${completed}, Failed: ${failed}`);
        
        // Wait between providers (shorter delay due to parallel processing)
        if (i < incompleteProviders.length - 1) {
            console.log('⏳ Waiting 3s before next provider...\n');
            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }
    
    // Final summary
    console.log('\n🎉 Enhanced Complete All Providers Script Finished!');
    console.log('==================================================');
    console.log(`📊 Total providers processed: ${incompleteProviders.length}`);
    console.log(`✅ Successfully completed: ${completed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`📊 Success rate: ${((completed / incompleteProviders.length) * 100).toFixed(1)}%`);
    
    // Rescan to show final status
    console.log('\n📊 Final Status:');
    const finalProviders = scanAllProviders();
    const stillIncomplete = finalProviders.filter(p => p.remainingGames > 0);
    
    if (stillIncomplete.length === 0) {
        console.log('🎉 ALL PROVIDERS ARE NOW COMPLETE!');
    } else {
        console.log(`⚠️ ${stillIncomplete.length} providers still need completion:`);
        stillIncomplete.slice(0, 10).forEach(p => {
            console.log(`   - ${p.name}: ${p.remainingGames} games remaining`);
        });
        if (stillIncomplete.length > 10) {
            console.log(`   ... and ${stillIncomplete.length - 10} more providers`);
        }
    }
}

// Run if called directly
if (require.main === module) {
    completeAllProvidersParallel().catch(error => {
        console.error('💥 Fatal error:', error.message);
        process.exit(1);
    });
}

module.exports = {
    completeAllProvidersParallel
};
