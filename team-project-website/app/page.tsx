import Navbar from "@/components/Navbar";
import Hero from "@/components/sections/Hero";
import Team from "@/components/sections/Team";
import Video from "@/components/sections/Video";
import Articles from "@/components/sections/Article";
import Extra from "@/components/sections/Extra";
import Footer from "@/components/Footer";

export default function Home() {
    return (
        <main>
            <Navbar />

            <Hero />
            <Team />
            <Video />
            <Articles />
            <Extra />

            <Footer />
        </main>
    );
}