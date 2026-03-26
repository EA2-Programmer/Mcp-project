'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Database, Terminal } from 'lucide-react';

const showcaseAssets = [
    { type: 'logo', content: 'TS' },
    { type: 'terminal', content: '// mcp_server_init... [OK]\n// connecting_mes_db... [OK]\n// port_secure_on: 9090' },
    { type: 'image', content: 'https://images.pexels.com/photos/257736/pexels-photo-257736.jpeg' },
];

export default function Hero() {
    const [index, setIndex] = useState(0);

    useEffect(() => {
        const timer = setInterval(() => {
            setIndex((prevIndex) => (prevIndex + 1) % showcaseAssets.length);
        }, 5000);
        return () => clearInterval(timer);
    }, []);

    const activeAsset = showcaseAssets[index];

    return (
        <section
            id="hero"
            className="relative min-h-screen flex items-center justify-center p-4 sm:p-6 lg:p-24 overflow-hidden pt-20 sm:pt-24"
        >
            {/* Background */}
            <div className="absolute inset-0 z-0 flex items-center justify-center">
                <div className="absolute inset-0 bg-black/70 z-10" />

                <AnimatePresence mode="wait">
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, scale: 1.1 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 1.5 }}
                        className="absolute inset-0 w-full h-full flex items-center justify-center"
                    >
                        {activeAsset.type === 'logo' && (
                            <div className="text-[20vw] sm:text-[25vw] font-black text-blue-600/10 select-none tracking-tighter">
                                {activeAsset.content}
                            </div>
                        )}

                        {activeAsset.type === 'terminal' && (
                            <pre className="text-gray-700/20 font-mono text-[3vw] sm:text-[2vw] leading-tight select-none whitespace-pre-wrap">
                                {activeAsset.content}
                            </pre>
                        )}

                        {activeAsset.type === 'image' && (
                            <img
                                src={activeAsset.content}
                                alt="System Showcase"
                                className="w-full h-full object-cover opacity-[0.05] filter grayscale"
                            />
                        )}
                    </motion.div>
                </AnimatePresence>
            </div>

            {/* Content */}
            <div className="relative z-10 text-center max-w-4xl px-4">
                <div className="inline-flex items-center gap-2 px-2 sm:px-3 py-1 rounded-full bg-blue-600/10 border border-blue-500/20 mb-4 sm:mb-6 group cursor-default">
                    <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-blue-500 animate-pulse" />
                    <span className="text-blue-400 font-mono text-[8px] sm:text-[10px] md:text-xs uppercase tracking-widest">
                        Model Context Protocol // TrackSys V1.0
                    </span>
                </div>

                <h1 className="text-3xl sm:text-5xl md:text-7xl font-extrabold text-white tracking-tighter leading-tight sm:leading-none mb-4 sm:mb-6">
                    Real-time MES Telemetry. <br className="hidden sm:block" /> Automated Intelligence.
                </h1>

                <p className="text-gray-400 text-sm sm:text-base md:text-lg max-w-2xl mx-auto mb-8 sm:mb-12 leading-relaxed px-2">
                    The TrackSys MCP Server bridges the gap between manufacturing data and Large Language Models, enabling automated reporting, instant troubleshooting, and predictive analytics.
                </p>

                <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 items-center justify-center">
                    <a
                        href="#video"
                        className="flex items-center gap-2 px-5 sm:px-8 py-3 sm:py-4 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-colors shadow-lg shadow-blue-600/20 group text-sm sm:text-base"
                    >
                        <Play size={16} className="sm:w-[20px] sm:h-[20px] text-blue-200 group-hover:scale-110 transition-transform" />
                        Explore Demo
                    </a>
                    <a
                        href="#team"
                        className="flex items-center gap-2 px-5 sm:px-8 py-3 sm:py-4 rounded-xl border border-white/10 text-gray-300 font-medium hover:border-white/30 hover:text-white transition group text-sm sm:text-base"
                    >
                        <Terminal size={16} className="sm:w-[18px] sm:h-[18px] text-gray-500 group-hover:text-gray-300" />
                        Meet the Engineers
                    </a>
                </div>
            </div>

            <div className="absolute bottom-0 left-0 w-full h-20 sm:h-32 bg-gradient-to-t from-black to-transparent z-20" />
        </section>
    );
}