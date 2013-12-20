
import os
import simplejson

COUNTER = 1
UTEMP = '/opt/plone/unex_exported_users'
GTEMP = '/opt/plone/unex_exported_groups'
GROUPS = {}
GROUP_NAMES = {}
USERS = {}
GROUPS_BLACKLIST = [
    'AuthenticatedUsers',
]


def export(self):
    setup_path(self)
    get_users_and_groups([self], 1)
    get_users_and_groups(walk_all(self), 0)
    store_users_and_groups()

    users_list = []
    for k, v in USERS.iteritems():
        props = v['_properties']
        fullname = props.get('title') or props.get('fullname') or k
        groups = ','.join(v['_user_groups'] or [])
        users_list.append("%s %s [%s]" % (k.ljust(20),
                                          fullname.ljust(50),
                                          groups))


    report =[
        "==============================",
        "Users and Groups export report",
        "==============================",
        "Found %s users" % len(USERS.keys()),
        "Users exported to %s" % UTEMP,
        "Found %s groups" % len(GROUPS.keys()),
        "Groups exported to %s" % GTEMP,
        "***********",
        "Items list",
        "***********",
        "GROUPS\n" + "\n".join(GROUPS.keys()),
        "-"*50,
        "USERS\n" + "\n".join(users_list),
    ]
    return "\n".join(report)


def setup_path(self):
    global UTEMP
    global GTEMP
    request = self.REQUEST
    path = request.get('path')
    if path:
        if not os.path.isdir(path):
            os.mkdir(path)
        UTEMP = os.path.join(path, 'users')
        if not os.path.isdir(UTEMP):
            os.mkdir(UTEMP)
        print "Exporting users to %s" % UTEMP
        GTEMP = os.path.join(path, 'groups')
        if not os.path.isdir(GTEMP):
            os.mkdir(GTEMP)
        print "Exporting groups to %s" % GTEMP


def walk_all(folder):
    for item_id in folder.objectIds():
        item = folder[item_id]
        yield item
        if getattr(item, 'objectIds', None) and \
           item.objectIds():
            for subitem in walk_all(item):
                yield subitem

def get_users_and_groups(items, root):
    global GROUPS
    global GROUP_NAMES
    global USERS
    for item in items:
        if item.__class__.__name__ == 'PloneSite' and \
                        not item.getId().startswith('copy_of'):
            charset = item.portal_properties.site_properties.default_charset
            properties = []
            if getattr(item, 'portal_groups', False):
                gtool = item.portal_groups
                if getattr(item, 'portal_groupdata', False):
                    gdtool = item.portal_groupdata
                    for pid in gdtool.propertyIds():
                        typ = gdtool.getPropertyType(pid)
                        properties.append((pid, typ))
                for group in item.portal_groups.listGroups():
                    if group.getId() in GROUPS_BLACKLIST:
                        print "SKIPPING blacklisted group", group.getId()
                        continue
                    group_name = str(group.getUserName())
                    if group.getUserName() in GROUPS.keys():
                        GROUP_NAMES[group_name] = 1
                        group_name = group_name+'_'+item.getId()
                        GROUP_NAMES[group_name] = 0
                    else:
                        GROUP_NAMES[group_name] = 0
                    group_data = {}
                    group_data['_groupname'] = group_name
                    roles = group.getRoles()
                    local_roles = item.__ac_local_roles__
                    if local_roles.get(group_name, False):
                        roles += tuple(local_roles[group_name])
                    ignoredset = set(['Authenticated', 'Member'])
                    roles = list(set(roles).difference(ignoredset))
                    group_data['_roles'] = roles
                    group_data['_plone_site'] = '/'.join(item.getPhysicalPath())
                    group_data['_properties'] = {}
                    group_data['_root_group'] = root
                    for pid, typ in properties:
                        val = group.getProperty(pid)
                        if typ in ('string', 'text'):
                            if getattr(val, 'decode', False):
                                try:
                                    val = val.decode(charset, 'ignore')
                                except UnicodeEncodeError:
                                    val = unicode(val)
                            else:
                                val = unicode(val)
                        group_data['_properties'][pid] = val
                    if getattr(group, 'getGroups', False):
                        groups = [g for g in group.getGroup().getGroups()
                                  if g not in GROUPS_BLACKLIST]
                        group_data['_group_groups'] = groups
                    GROUPS[group_name] = group_data
            if not getattr(item, 'portal_membership', False):
                continue
            properties = []
            if  getattr(item, 'portal_memberdata', False):
                mdtool = item.portal_memberdata
                for pid in mdtool.propertyIds():
                    typ = mdtool.getPropertyType(pid)
                    properties.append((pid, typ))
            try:
                # plone 3
                passwdlist = item.acl_users.source_users._user_passwords
            except:
                passwdlist = None
            for member in item.portal_membership.listMembers():
                user_data = {}
                user_name = str(member.getUserName())
                user_data['_username'] = user_name
                user = member.getUser()
                try:
                    pwd = user._getPassword()
                except (AttributeError, NotImplementedError):
                    # plone 3
                    pwd = passwdlist and passwdlist[user_name] or ''
                user_data['_password'] = str(pwd)
                user_data['_root_user'] = root
                user_data['_root_roles'] = []
                user_data['_local_roles'] = []
                if root:
                    user_data['_root_roles'] = [r for r in member.getRoles()
                                                if not r in ['Authenticated',]]
                else:
                    roles = member.getRoles()
                    local_roles = item.__ac_local_roles__
                    if local_roles.get(user_name, False):
                        roles += tuple(local_roles[user_name])
                    ignoredset = set()
                    roles = list(set(roles).difference(ignoredset))
                    user_data['_local_roles'] = roles
                user_data['_user_groups'] = []
                user_data['_plone_site'] = '/'.join(item.getPhysicalPath())
                if getattr(member, 'getGroups', False):
                    user_data['_user_groups'] = [g for g in member.getGroups()
                                                 if not g in GROUPS_BLACKLIST]
                user_data['_properties'] = {}
                for pid, typ in properties:
                    val = member.getProperty(pid)
                    if typ in ('string', 'text'):
                        if getattr(val, 'decode', False):
                            try:
                                val = val.decode(charset, 'ignore')
                            except UnicodeEncodeError:
                                val = unicode(val)
                        else:
                            val = unicode(val)
                    if typ == 'date':
                        val = str(val)
                    user_data['_properties'][pid] = val
                USERS[user_name] = user_data

def store_users_and_groups():
    global GROUPS
    global USERS
    global COUNTER
    for group_name, group_data in GROUPS.iteritems():
        group = fix_group_names((group_data['_groupname'],), group_data)[0]
        group_data['_groupname'] = group
        groups = fix_group_names(group_data['_group_groups'], group_data)
        group_data['_group_groups'] = groups
        write(group_data, GTEMP)
        print '   |--> '+str(COUNTER)+' - '+str(group_data['_groupname'])+' IN: '+group_data['_plone_site']
        COUNTER += 1
    for user_name, user_data in USERS.iteritems():
        groups = fix_group_names(user_data['_user_groups'], user_data)
        user_data['_user_groups'] = groups
        write(user_data, UTEMP)
        COUNTER += 1
        print '   |--> '+str(COUNTER)+' - '+str(user_data['_username'])+' IN: '+user_data['_plone_site']
    print '----------------------------  --------------------------------------'


def fix_group_names(groupnames, data):
    groups = []
    for group in groupnames:
        rgroup = group.replace(' ', '-')
        try:
            if GROUP_NAMES[group]:
                groups.append(rgroup+'_'+data['_plone_site'].strip('/').split('/')[-1])
            else:
                groups.append(rgroup)
        except:
            import pdb;pdb.set_trace()
    print groups
    return groups


def write(item, temp):
    SUBTEMP = str(COUNTER/1000) # 1000 files per folder
    if not os.path.isdir(os.path.join(temp, SUBTEMP)):
        os.mkdir(os.path.join(temp, SUBTEMP))

    f = open(os.path.join(temp, SUBTEMP, str(COUNTER % 1000)+'.json'), 'wb')
    simplejson.dump(item, f, indent=4)
    f.close()
