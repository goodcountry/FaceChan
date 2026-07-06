/**
 * FederatedBadge — small marker shown right after a poster's name when
 * their post originated on a remote federated instance (author.is_remote).
 * Mirrors the styling convention of BadgeDisplay's user-badge classes.
 */
export default function FederatedBadge({ author }) {
  if (!author?.is_remote) return null
  return (
    <span className="user-badge badge-federated" title="Posted from a federated instance">
      ⇄ Federated
    </span>
  )
}
