import { useEffect, useRef, useState } from 'react'
export default function ChatBox({ bubbles }) {
    const ref = useRef(null)
    const [pinned, setPinned] = useState(true)
    useEffect(() => {
        const el = ref.current
        if (el && pinned) el.scrollTop = el.scrollHeight
    }, [bubbles, pinned])
    const onScroll = () => {
        const el = ref.current
        if (el) setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 48)
    }
    const toLatest = () => {
        const el = ref.current
        if (el) el.scrollTop = el.scrollHeight
        setPinned(true)
    }
    return (
        <div className="chat-wrap">
            <div
                className="chat"
                ref={ref}
                onScroll={onScroll}
                role="log"
                aria-live="polite"
                aria-label="Conversation transcript"
            >
                {bubbles.length === 0 && <p className="muted center">The conversation will appear here.</p>}
                {bubbles.map((b) => (
                    <div key={b.id} className={`bubble ${b.speaker} ${b.isFinal ? '' : 'interim'}`}>
                        <span className="who">{b.speaker === 'user' ? 'You' : 'Agent'}</span>
                        <p>{b.text}</p>
                    </div>
                ))}
            </div>
            {!pinned && (
                <button className="to-latest" onClick={toLatest}>
                    Scroll to latest ↓
                </button>
            )}
        </div>
    )
}
