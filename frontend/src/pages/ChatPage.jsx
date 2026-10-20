import { useParams } from 'react-router-dom'
import PastCall from '../components/PastCall/PastCall'
export default function ChatPage() {
    const { id = '' } = useParams()
    return <PastCall id={id} />
}
