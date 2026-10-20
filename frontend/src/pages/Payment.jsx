import { useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { errorMessage, usePayAgentMutation } from '../api/api'

export default function Payment() {
    const { me } = useOutletContext()
    const { aid } = useParams()
    const navigate = useNavigate()
    const [amount, setAmount] = useState('')
    const [error, setError] = useState(null)
    const [pay, { isLoading }] = usePayAgentMutation()
    const submit = async (e) => {
        e.preventDefault()
        setError(null)
        try {
            await pay({ uid: me.uid, aid, amount }).unwrap()
            navigate(`/agents/${me.uid}`)
        } catch (err) {
            setError(errorMessage(err, 'Payment failed. Please try again.'))
        }
    }
    return (
        <div className="center-box-page">
            <form className="box" onSubmit={(e) => void submit(e)}>
                <h1>Payment</h1>
                {error && (
                    <div className="banner error" role="alert">
                        {error}
                    </div>
                )}
                <label>
                    Enter amount
                    <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        min="0"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        required
                    />
                </label>
                <div className="box-actions">
                    <button type="button" onClick={() => navigate(`/agents/${me.uid}`)}>
                        Cancel
                    </button>
                    <button className="primary" disabled={isLoading || amount === ''}>
                        {isLoading ? 'Processing…' : 'Pay'}
                    </button>
                </div>
            </form>
        </div>
    )
}
