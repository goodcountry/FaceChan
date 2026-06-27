/**
 * UserLink — renders a display name as a link to the public profile,
 * or plain "Anonymous" text if no author is attached to the post.
 * The link uses the stable username for routing; display_name is shown.
 */
import { Link } from 'react-router-dom'

export default function UserLink({ author, className = 'fb-author' }) {
  if (!author?.username) {
    return <span className={className}>Anonymous</span>
  }
  const displayName = author.display_name || author.username
  return (
    <Link to={`/user/${author.username}`} className={`${className} user-link`}>
      {displayName}
    </Link>
  )
}
