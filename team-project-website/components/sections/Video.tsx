export default function Video() {
    return (
        <section id="video" className="min-h-screen p-10">
            <h2 className="text-3xl font-bold mb-10 text-center">
                Video
            </h2>

            <div className="flex justify-center">
                <video
                    controls
                    className="w-full max-w-3xl rounded-xl border border-[#222]"
                >
                    <source src="/videos/demo.mp4" type="video/mp4" />
                </video>
            </div>
        </section>
    );
}