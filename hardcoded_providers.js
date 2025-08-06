/**
 * Hardcoded Providers Module
 * Contains the 49 real game providers from Stake.com
 */

// Real game providers from Stake.com (49 total)
const STAKE_PROVIDERS = [
    { slug: "pragmatic-play", name: "Pragmatic Play" },
    { slug: "stake-originals", name: "Stake Originals" },
    { slug: "hacksaw-gaming", name: "Hacksaw Gaming" },
    { slug: "evolution-gaming", name: "Evolution Gaming" },
    { slug: "no-limit-city", name: "No Limit City" },
    { slug: "massive-studios", name: "Massive Studios" },
    { slug: "twist-gaming", name: "Twist Gaming" },
    { slug: "titan-gaming", name: "Titan Gaming" },
    { slug: "backseat-gaming", name: "Backseat Gaming" },
    { slug: "b-gaming", name: "B Gaming" },
    { slug: "push-gaming", name: "Push Gaming" },
    { slug: "hacksaw-openrgs", name: "Hacksaw OpenRGS" },
    { slug: "stake-engine", name: "Stake Engine" },
    { slug: "shady-lady", name: "Shady Lady" },
    { slug: "relax-gaming", name: "Relax Gaming" },
    { slug: "avatarux", name: "Avatarux" },
    { slug: "thunderkick", name: "Thunderkick" },
    { slug: "penguin-king", name: "Penguin King" },
    { slug: "fat-panda", name: "Fat Panda" },
    { slug: "peter-sons", name: "Peter & Sons" },
    { slug: "playn-go", name: "Play'n GO" },
    { slug: "popiplay", name: "Popiplay" },
    { slug: "paperclip-gaming", name: "Paperclip Gaming" },
    { slug: "elk-studios", name: "Elk Studios" },
    { slug: "print-studios", name: "Print Studios" },
    { slug: "bullshark-games", name: "Bullshark Games" },
    { slug: "netent", name: "NetEnt" },
    { slug: "big-time-gaming", name: "Big Time Gaming" },
    { slug: "red-tiger", name: "Red Tiger" },
    { slug: "pg-soft", name: "PG Soft" },
    { slug: "onetouch", name: "OneTouch" },
    { slug: "slotmill", name: "Slotmill" },
    { slug: "live88", name: "Live88" },
    { slug: "gamomat", name: "Gamomat" },
    { slug: "3-oaks-gaming", name: "3 Oaks Gaming" },
    { slug: "games-global", name: "Games Global" },
    { slug: "endorphina", name: "Endorphina" },
    { slug: "voltent", name: "VoltEnt" },
    { slug: "just-slots", name: "Just Slots" },
    { slug: "fantasma-games", name: "Fantasma Games" },
    { slug: "blueprint", name: "Blueprint" },
    { slug: "belatra", name: "Belatra" },
    { slug: "playson", name: "Playson" },
    { slug: "novomatic", name: "Novomatic" },
    { slug: "skywind", name: "Skywind" },
    { slug: "quickspin", name: "Quickspin" },
    { slug: "red-rake-gaming", name: "Red Rake Gaming" },
    { slug: "game-art", name: "Game Art" },
    { slug: "spinomenal", name: "Spinomenal" }
];

// Game categories/types (not actual providers)
const GAME_CATEGORIES = new Set([
    'slots', 'table-games', 'live-casino', 'blackjack', 'baccarat', 'roulette',
    'video-poker', 'cards', 'dice', 'game-shows', 'scratch-cards',
    'bonus-buy', 'megaways', 'new-releases', 'enhanced-rtp', 'jackpot-slots'
]);

// Create lookup sets for fast validation
const REAL_PROVIDER_SLUGS = new Set(STAKE_PROVIDERS.map(p => p.slug));
const PROVIDER_NAME_MAP = new Map(STAKE_PROVIDERS.map(p => [p.slug, p.name]));

/**
 * Get all hardcoded providers
 */
function getAllProviders() {
    return STAKE_PROVIDERS;
}

/**
 * Check if a slug is a real provider
 */
function isRealProvider(slug) {
    return REAL_PROVIDER_SLUGS.has(slug);
}

/**
 * Check if a slug is a game category (not a provider)
 */
function isGameCategory(slug) {
    return GAME_CATEGORIES.has(slug);
}

/**
 * Get provider name by slug
 */
function getProviderName(slug) {
    return PROVIDER_NAME_MAP.get(slug) || null;
}

/**
 * Filter providers list to only include real providers
 */
function filterRealProviders(providers) {
    return providers.filter(provider => {
        const slug = typeof provider === 'string' ? provider : provider.slug;
        return isRealProvider(slug);
    });
}

/**
 * Validate and log provider status
 */
function validateProvider(slug) {
    if (isRealProvider(slug)) {
        console.log(`✅ Valid provider: ${getProviderName(slug)} (${slug})`);
        return true;
    } else if (isGameCategory(slug)) {
        console.log(`❌ Game category (not provider): ${slug}`);
        return false;
    } else {
        console.log(`❓ Unknown provider/category: ${slug}`);
        return false;
    }
}

/**
 * Get provider statistics
 */
function getProviderStats() {
    return {
        totalRealProviders: STAKE_PROVIDERS.length,
        totalGameCategories: GAME_CATEGORIES.size,
        realProviderSlugs: Array.from(REAL_PROVIDER_SLUGS),
        gameCategories: Array.from(GAME_CATEGORIES)
    };
}

module.exports = {
    STAKE_PROVIDERS,
    GAME_CATEGORIES,
    REAL_PROVIDER_SLUGS,
    PROVIDER_NAME_MAP,
    getAllProviders,
    isRealProvider,
    isGameCategory,
    getProviderName,
    filterRealProviders,
    validateProvider,
    getProviderStats
};
