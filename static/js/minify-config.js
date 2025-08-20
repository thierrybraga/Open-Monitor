/**
 * JavaScript Minification and Optimization Configuration
 * Configura a minificação e otimização de arquivos JavaScript
 */

const MinifyConfig = {
    // Arquivos para minificação
    files: {
        // Arquivos críticos (carregamento imediato)
        critical: [
            'static/js/base.js',
            'static/js/theme.js',
            'static/js/loading-manager.js',
            'static/js/performance-optimizer.js'
        ],
        
        // Arquivos para lazy loading
        lazy: [
            'static/js/views/analytics_view.js',
            'static/js/views/search_view.js',
            'static/js/views/reports_view.js',
            'static/js/views/newsletter_view.js',
            'static/js/vulnerabilities.js',
            'static/js/responsive.js'
        ],
        
        // Arquivos de modelos
        models: [
            'static/js/models/analytics_model.js',
            'static/js/models/search_model.js'
        ],
        
        // Arquivos de controladores
        controllers: [
            'static/js/controllers/analytics_controller.js',
            'static/js/controllers/search_controller.js',
            'static/js/controllers/newsletter_controller.js'
        ]
    },
    
    // Configurações de otimização
    optimization: {
        // Minificação
        minify: {
            enabled: true,
            removeComments: true,
            removeWhitespace: true,
            shortenVariables: true,
            removeDeadCode: true
        },
        
        // Compressão
        compression: {
            enabled: true,
            gzip: true,
            brotli: true
        },
        
        // Tree shaking
        treeShaking: {
            enabled: true,
            removeUnusedExports: true,
            removeUnusedImports: true
        },
        
        // Code splitting
        codeSplitting: {
            enabled: true,
            chunkSize: 50000, // 50KB
            maxChunks: 10
        }
    },
    
    // Configurações de cache
    cache: {
        enabled: true,
        strategy: 'content-hash',
        maxAge: 31536000, // 1 ano
        immutable: true
    },
    
    // Source maps
    sourceMaps: {
        enabled: process.env.NODE_ENV !== 'production',
        inline: false,
        separate: true
    },
    
    // Análise de bundle
    analysis: {
        enabled: true,
        generateReport: true,
        showDuplicates: true,
        showUnused: true
    }
};

// Função para gerar configuração de build
function generateBuildConfig() {
    const config = {
        entry: {},
        output: {
            path: 'static/dist/js',
            filename: '[name].[contenthash].js',
            chunkFilename: '[name].[contenthash].chunk.js'
        },
        optimization: {
            minimize: MinifyConfig.optimization.minify.enabled,
            splitChunks: {
                chunks: 'all',
                maxSize: MinifyConfig.optimization.codeSplitting.chunkSize,
                cacheGroups: {
                    vendor: {
                        test: /[\\/]node_modules[\\/]/,
                        name: 'vendors',
                        chunks: 'all'
                    },
                    common: {
                        name: 'common',
                        minChunks: 2,
                        chunks: 'all',
                        enforce: true
                    }
                }
            }
        },
        devtool: MinifyConfig.sourceMaps.enabled ? 'source-map' : false
    };
    
    // Adiciona entradas para arquivos críticos
    MinifyConfig.files.critical.forEach(file => {
        const name = file.split('/').pop().replace('.js', '');
        config.entry[`critical-${name}`] = `./${file}`;
    });
    
    // Adiciona entradas para arquivos lazy
    MinifyConfig.files.lazy.forEach(file => {
        const name = file.split('/').pop().replace('.js', '');
        config.entry[`lazy-${name}`] = `./${file}`;
    });
    
    return config;
}

// Função para otimizar arquivos individuais
function optimizeFile(filePath, content) {
    let optimized = content;
    
    if (MinifyConfig.optimization.minify.enabled) {
        // Remove comentários
        if (MinifyConfig.optimization.minify.removeComments) {
            optimized = optimized.replace(/\/\*[\s\S]*?\*\//g, '');
            optimized = optimized.replace(/\/\/.*$/gm, '');
        }
        
        // Remove espaços em branco desnecessários
        if (MinifyConfig.optimization.minify.removeWhitespace) {
            optimized = optimized.replace(/\s+/g, ' ');
            optimized = optimized.replace(/;\s*}/g, '}');
            optimized = optimized.replace(/\s*{\s*/g, '{');
        }
    }
    
    return optimized;
}

// Função para gerar hash de conteúdo
function generateContentHash(content) {
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
        const char = content.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(16);
}

// Função para analisar dependências
function analyzeDependencies(content) {
    const imports = [];
    const exports = [];
    
    // Encontra imports
    const importRegex = /import\s+.*?from\s+['"]([^'"]+)['"]/g;
    let match;
    while ((match = importRegex.exec(content)) !== null) {
        imports.push(match[1]);
    }
    
    // Encontra exports
    const exportRegex = /export\s+(?:default\s+)?([\w\s,{}]+)/g;
    while ((match = exportRegex.exec(content)) !== null) {
        exports.push(match[1]);
    }
    
    return { imports, exports };
}

// Exporta configuração
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        MinifyConfig,
        generateBuildConfig,
        optimizeFile,
        generateContentHash,
        analyzeDependencies
    };
} else {
    window.MinifyConfig = {
        MinifyConfig,
        generateBuildConfig,
        optimizeFile,
        generateContentHash,
        analyzeDependencies
    };
}