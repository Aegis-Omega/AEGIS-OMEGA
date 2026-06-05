import { useState, useEffect } from 'react'

export interface UserTier {
  plan: 'free' | 'pro' | 'enterprise'
  dailyLimit: number
  monthlyLimit: number
  currentDailyUsage: number
  currentMonthlyUsage: number
  resetAt: number
  stripeSessionId?: string
  paymentMethod?: string
}

const TIER_LIMITS = {
  free: { daily: 5, monthly: 150 },
  pro: { daily: 1000, monthly: 30000 },
  enterprise: { daily: Infinity, monthly: Infinity },
}

export function useTokenCounter() {
  const [tier, setTier] = useState<UserTier>(() => {
    const stored = localStorage.getItem('aegis_tier')
    if (stored) {
      try {
        return JSON.parse(stored) as UserTier
      } catch {
        // Corrupted data, reset
      }
    }

    return {
      plan: 'free',
      dailyLimit: TIER_LIMITS.free.daily,
      monthlyLimit: TIER_LIMITS.free.monthly,
      currentDailyUsage: 0,
      currentMonthlyUsage: 0,
      resetAt: Date.now() + 86400000,
    }
  })

  // Reset daily counter at midnight UTC
  useEffect(() => {
    const now = Date.now()
    if (now > tier.resetAt) {
      const updated: UserTier = {
        ...tier,
        currentDailyUsage: 0,
        resetAt: now + 86400000,
      }
      setTier(updated)
      localStorage.setItem('aegis_tier', JSON.stringify(updated))
    }
  }, [tier])

  const canSendMessage = (): boolean => {
    if (tier.currentDailyUsage >= tier.dailyLimit) return false
    if (tier.currentMonthlyUsage >= tier.monthlyLimit) return false
    return true
  }

  const getRemainingMessages = (): number => {
    const dailyRemaining = tier.dailyLimit - tier.currentDailyUsage
    const monthlyRemaining = tier.monthlyLimit - tier.currentMonthlyUsage
    return Math.min(dailyRemaining, monthlyRemaining)
  }

  const incrementUsage = () => {
    const updated: UserTier = {
      ...tier,
      currentDailyUsage: tier.currentDailyUsage + 1,
      currentMonthlyUsage: tier.currentMonthlyUsage + 1,
    }
    setTier(updated)
    localStorage.setItem('aegis_tier', JSON.stringify(updated))
  }

  const startStripeCheckout = async (plan: 'pro' | 'enterprise') => {
    try {
      const res = await fetch('/api/stripe-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      })
      const data = await res.json()
      if (data.sessionUrl) {
        window.location.href = data.sessionUrl
      } else if (data.error) {
        console.error('Stripe error:', data.error)
      }
    } catch (err) {
      console.error('Stripe checkout failed:', err)
    }
  }

  const upgradeToTier = (newPlan: 'pro' | 'enterprise') => {
    startStripeCheckout(newPlan)
  }

  const setTierFromPayment = (newPlan: 'pro' | 'enterprise', sessionId: string) => {
    const limits = TIER_LIMITS[newPlan]
    const updated: UserTier = {
      plan: newPlan,
      dailyLimit: limits.daily,
      monthlyLimit: limits.monthly,
      currentDailyUsage: 0,
      currentMonthlyUsage: 0,
      resetAt: Date.now() + 86400000,
      stripeSessionId: sessionId,
    }
    setTier(updated)
    localStorage.setItem('aegis_tier', JSON.stringify(updated))
  }

  return {
    tier,
    canSendMessage,
    getRemainingMessages,
    incrementUsage,
    upgradeToTier,
    setTierFromPayment,
  }
}
