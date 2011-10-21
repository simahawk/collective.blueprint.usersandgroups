import os

try:
    import json
except ImportError:
    import simplejson as json

from AccessControl.interfaces import IRoleManager

from zope.interface import implements, classProvides

from Products.CMFCore.utils import getToolByName

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import resolvePackageReferenceOrFile


class JSONSource(object):
    """
    loads users/groups exported trough export_scripts/plone2.0_export.py
    it's a modified version of collective.jsonmigrator.jsonsource
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        self.path = resolvePackageReferenceOrFile(options['path'])
        if self.path is None or not os.path.isdir(self.path):
            raise Exception, 'Path ('+str(self.path)+') does not exists.'

    def __iter__(self):
        for item in self.previous:
            yield item

        item3_list = [int(i)
                      for i in os.listdir(self.path)
                      if not i.startswith('.')]
        for item3 in sorted(item3_list):
            item3_path = os.path.join(self.path, str(item3))

            item2_list = [int(j[:-5])
                          for j in os.listdir(item3_path)
                          if j.endswith('.json')]
            for item2 in sorted(item2_list):
                item2_path = os.path.join(self.path,
                                          str(item3),
                                          str(item2)+'.json')
                f = open(item2_path)
                item = json.loads(f.read())
                f.close()

                yield item


class CreateRoles(object):
    """ Loops trough roles assigned to users/groups
    (by any of the '*_roles' keys) and create them if do not exist.
    This should be run *before* CreateUser and/or CreateGroup
    """

    implements(ISection)
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.portal = getToolByName(self.context, 'portal_url').getPortalObject()
        self.acl_users = getToolByName(self.context, 'acl_users')

    def __iter__(self):
        for item in self.previous:
            roles = item.get('_roles',[])
            roles += item.get('_root_roles',[])
            roles += item.get('_local_roles',[])
            for role in set(roles):
                if not role in self.portal.valid_roles():
                    self.portal._addRole(role)
                    try:
                        # see
                        # http://repositorio.interlegis.gov.br/ILSAAP/trunk/InstallUtils/installers/installRoles.py
                        # and
                        # http://stackoverflow.com/questions/7769242/how-to-add-a-portal-role-by-python-code
                        self.acl_users.portal_role_manager.addRole(role)
                    except:
                        pass
            yield item


class CreateUser(object):
    """ """

    implements(ISection)
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.regtool = getToolByName(self.context, 'portal_registration')

    def __iter__(self):
        for item in self.previous:
            if '_password' not in item.keys() or \
               '_username' not in item.keys():
                yield item; continue

            if self.regtool.isMemberIdAllowed(item['_username']):
                self.regtool.addMember(item['_username'],
                                item['_password'].encode('utf-8'))
            yield item


class CreateGroup(object):
    """ """

    implements(ISection)
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.gtool = getToolByName(self.context, 'portal_groups')

    def __iter__(self):
        for item in self.previous:
            if item.get('_groupname', False):
                self.gtool.addGroup(item['_groupname'])
            yield item


class UpdateUserProperties(object):
    """ """

    implements(ISection)
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.memtool = getToolByName(self.context, 'portal_membership')
        self.gtool = getToolByName(self.context, 'portal_groups')
        self.portal = getToolByName(self.context, 'portal_url').getPortalObject()

    def __iter__(self):
        for item in self.previous:

            if '_username' in item.keys():
                member = self.memtool.getMemberById(item['_username'])
                if not member:
                    yield item; continue
                member.setMemberProperties(item['_properties'])

                # add member to group
                if item.get('_user_groups', False):
                    for groupid in item['_user_groups']:
                        group = self.gtool.getGroupById(groupid)
                        if group:
                            group.addMember(item['_username'])

                # setting global roles
                if item.get('_root_roles', False):
                    self.portal.acl_users.userFolderEditUser(
                                item['_username'],
                                None,
                                item['_root_roles'])

                # setting local roles
                if item.get('_local_roles', False):
                    try:
                        obj = self.portal.unrestrictedTraverse(item['_plone_site'])
                    except (AttributeError, KeyError):
                        pass
                    else:
                        if IRoleManager.providedBy(obj):
                            obj.manage_addLocalRoles(item['_username'], item['_local_roles'])
                            obj.reindexObjectSecurity()

            yield item


class UpdateGroupProperties(object):
    """ """

    implements(ISection)
    classProvides(ISectionBlueprint)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.gtool = getToolByName(self.context, 'portal_groups')
        self.portal = getToolByName(self.context, 'portal_url').getPortalObject()

    def __iter__(self):
        for item in self.previous:
            if not item.get('_groupname', False):
                yield item; continue

            group = self.gtool.getGroupById(item['_groupname'])
            if not group:
                yield item; continue

            if item.get('_root_group', False):
                self.gtool.editGroup(item['_groupname'],
                                    roles=item['_roles'])
            elif item.get('_roles', False):

                # setting local roles
                try:
                    obj = self.portal.unrestrictedTraverse(item['_plone_site'])
                except (AttributeError, KeyError):
                    pass
                else:
                    if IRoleManager.providedBy(obj):
                        obj.manage_addLocalRoles(item['_groupname'], item['_roles'])
                        obj.reindexObjectSecurity()

            if item.get('_group_groups', False):
                try:
                    self.gtool.editGroup(item['_groupname'],
                                    groups=item.get('_group_groups', []))
                except:
                    pass

            # With PlonePAS > 4.0b3, mutable_properties.enumerateUsers doesn't
            # return groups anymore, so it isn't possible to search a group
            # by its title stored in mutable_properties. Only the
            # title in source_groups is searched.
            # editGroup modify the title and description in source_groups
            # plugin, then it calls setGroupProperties(kw) which set the
            # properties on the mutable_properties plugin.
            if '_properties' in item:
                self.gtool.editGroup(item['_groupname'],
                                     **item['_properties'])
            yield item
