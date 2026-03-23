'use client';
import { useEffect, useState } from 'react';

export default function Navbar() {
    const [activeSection, setActiveSection] = useState('hero');
    const navLinks = [
        { name: 'Terminal', id: 'hero' },
        { name: 'Engineers', id: 'team' },
        { name: 'System_Demo', id: 'video' },
        { name: 'Documentation', id: 'articles' }
    ];

    useEffect(() => {
        const handleScroll = () => {
            const current = navLinks.find(link => {
                const el = document.getElementById(link.id);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    // Detects if the section is in the middle of the viewport
                    return rect.top <= 150 && rect.bottom >= 150;
                }
                return false;
            });
            if (current) setActiveSection(current.id);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <nav className="fixed top-0 left-0 w-full z-50 backdrop-blur-xl bg-black/60 border-b border-white/5">
            <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">

                {/* --- CLICKABLE TRACKSYS LOGO --- */}
                <a
                    href="#hero"
                    onClick={() => setActiveSection('hero')}
                    className="flex items-center gap-3 group cursor-pointer no-underline"
                >
                    <div className="relative w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center shadow-[0_0_20px_rgba(37,99,235,0.3)] group-hover:bg-blue-500 transition-colors duration-300">
                        <span className="text-white font-black text-xl select-none">T</span>
                        <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-black animate-pulse" />
                    </div>
                    <div className="hidden sm:block">
                        <h1 className="text-white font-bold tracking-tighter leading-none group-hover:text-blue-400 transition-colors">TRACKSYS</h1>
                        <p className="text-[10px] font-mono text-blue-500 tracking-[0.2em] group-hover:text-blue-300 transition-colors">MCP_SERVER_OS</p>
                    </div>
                </a>

                {/* HUD NAV LINKS */}
                <ul className="flex items-center gap-2 sm:gap-6">
                    {navLinks.map((link) => (
                        <li key={link.id}>
                            <a href={`#${link.id}`} className="relative px-4 py-2 transition-all duration-300 group">
                                <span className={`relative z-10 font-mono text-[11px] tracking-widest uppercase ${activeSection === link.id ? 'text-blue-400' : 'text-gray-500 group-hover:text-white'}`}>
                                    {link.name}
                                </span>
                                {activeSection === link.id && (
                                    <>
                                        <span className="absolute inset-0 bg-blue-500/10 rounded-md blur-sm" />
                                        <span className="absolute top-0 left-0 w-2 h-2 border-t border-l border-blue-500" />
                                        <span className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-blue-500" />
                                    </>
                                )}
                            </a>
                        </li>
                    ))}
                </ul>
            </div>
        </nav>
    );
}