'use client';
import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';

export default function Navbar() {
    const [activeSection, setActiveSection] = useState('hero');
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const navLinks = [
        { name: 'Terminal', id: 'hero' },
        { name: 'Engineers', id: 'team' },
        { name: 'System_Demo', id: 'video' },
        { name: 'Article', id: 'articles' }
    ];

    useEffect(() => {
        const handleScroll = () => {
            const current = navLinks.find(link => {
                const el = document.getElementById(link.id);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    return rect.top <= 150 && rect.bottom >= 150;
                }
                return false;
            });
            if (current) setActiveSection(current.id);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLinkClick = (id: string) => {
        setActiveSection(id);
        setIsMenuOpen(false);
        const element = document.getElementById(id);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth' });
        }
    };

    return (
        <nav className="fixed top-0 left-0 w-full z-50 backdrop-blur-xl bg-black/60 border-b border-white/5">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 sm:h-20 flex items-center justify-between">

                {/* Logo */}
                <a
                    href="#hero"
                    onClick={(e) => {
                        e.preventDefault();
                        handleLinkClick('hero');
                    }}
                    className="flex items-center gap-2 sm:gap-3 group cursor-pointer no-underline"
                >
                    <div className="relative w-8 h-8 sm:w-10 sm:h-10 bg-blue-600 rounded-lg flex items-center justify-center shadow-[0_0_20px_rgba(37,99,235,0.3)] group-hover:bg-blue-500 transition-colors duration-300">
                        <span className="text-white font-black text-lg sm:text-xl select-none">T</span>
                        <div className="absolute -top-1 -right-1 w-2 h-2 sm:w-3 sm:h-3 bg-green-500 rounded-full border-2 border-black animate-pulse" />
                    </div>
                    <div className="hidden sm:block">
                        <h1 className="text-white font-bold tracking-tighter leading-none group-hover:text-blue-400 transition-colors text-sm sm:text-base">TRACKSYS</h1>
                        <p className="text-[8px] sm:text-[10px] font-mono text-blue-500 tracking-[0.2em] group-hover:text-blue-300 transition-colors">MCP_SERVER_OS</p>
                    </div>
                </a>

                {/* Desktop Navigation */}
                <ul className="hidden md:flex items-center gap-2 sm:gap-6">
                    {navLinks.map((link) => (
                        <li key={link.id}>
                            <a
                                href={`#${link.id}`}
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleLinkClick(link.id);
                                }}
                                className="relative px-3 sm:px-4 py-2 transition-all duration-300 group cursor-pointer"
                            >
                                <span className={`relative z-10 font-mono text-[10px] sm:text-[11px] tracking-widest uppercase ${activeSection === link.id ? 'text-blue-400' : 'text-gray-500 group-hover:text-white'}`}>
                                    {link.name}
                                </span>
                                {activeSection === link.id && (
                                    <>
                                        <span className="absolute inset-0 bg-blue-500/10 rounded-md blur-sm" />
                                        <span className="absolute top-0 left-0 w-1.5 h-1.5 border-t border-l border-blue-500" />
                                        <span className="absolute bottom-0 right-0 w-1.5 h-1.5 border-b border-r border-blue-500" />
                                    </>
                                )}
                            </a>
                        </li>
                    ))}
                </ul>

                {/* Mobile Hamburger Button */}
                <button
                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                    className="md:hidden relative z-50 p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition"
                >
                    {isMenuOpen ? <X size={20} className="text-white" /> : <Menu size={20} className="text-white" />}
                </button>

                {/* Mobile Menu Overlay */}
                {isMenuOpen && (
                    <div className="fixed top-16 left-0 right-0 bg-black/95 backdrop-blur-xl border-b border-white/10 md:hidden z-40 animate-in slide-in-from-top duration-300">
                        <ul className="flex flex-col py-4">
                            {navLinks.map((link) => (
                                <li key={link.id}>
                                    <a
                                        href={`#${link.id}`}
                                        onClick={(e) => {
                                            e.preventDefault();
                                            handleLinkClick(link.id);
                                        }}
                                        className={`block px-6 py-4 font-mono text-sm tracking-widest uppercase transition ${
                                            activeSection === link.id 
                                                ? 'text-blue-400 bg-blue-500/10' 
                                                : 'text-gray-400 hover:text-white hover:bg-white/5'
                                        }`}
                                    >
                                        {link.name}
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </nav>
    );
}